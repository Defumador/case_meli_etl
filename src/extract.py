import logging
import re
import requests

logger = logging.getLogger(__name__)


def _chunks(seq, size):
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


def _as_list(value):
    if not value:
        return []
    return [value] if isinstance(value, str) else list(value)


def _reached(count, limit):
    return bool(limit) and count >= limit


def _total(data):
    return (data.get('paging') or {}).get('total', 0)


def _paginate(fetch, page_size, max_offset=None):
    offset = 0
    while True:
        if max_offset is not None and offset > max_offset:
            logger.warning('Limite de paginação da API atingido (offset máximo %s)', max_offset)
            return

        data = fetch(page_size, offset)
        page = data.get('results', [])
        if not page:
            return

        total = _total(data)
        yield page, total

        offset += page_size
        if len(page) < page_size or (total and offset >= total):
            return


def get_attribute(product, attribute_id):
    return next(
        (
            attr.get('value_name') or ''
            for attr in product.get('attributes', [])
            if attr.get('id') == attribute_id
        ),
        '',
    )


def extract_configured_attributes(product, cfg):
    requested = set(
        _as_list(cfg['product'].get('attributes', []))
    )

    return {
        attr['id']: attr.get('value_name')
        for attr in product.get('attributes', [])
        if attr.get('id') in requested
        and attr.get('value_name') is not None
    }

def query_matches(product, models):
    if not models:
        return True

    tokens = set(re.findall(r'\w+', (product.get('name') or '').casefold()))

    for target in models:
        terms = re.findall(r'\w+', target.casefold())
        if terms and all(term in tokens for term in terms):
            return True

    return False


def filter_products(products, cfg):
    p = cfg['product']

    brands = {brand.strip().casefold() for brand in _as_list(p.get('brand')) if brand.strip()}
    models = _as_list(p.get('query'))

    return [
        product
        for product in products
        if (not brands or get_attribute(product, 'BRAND').strip().casefold() in brands)
        and query_matches(product, models)
    ]


def extract_products(client, cfg):
    p = cfg['product']
    s = cfg['search']
    page_size = s['page_size']
    max_products = s.get('max_products')
    max_offset = s.get('max_offset', 100)
    category = f"{s['site']}-{p['category']}" if p.get('category') else None   # opcional
    condition = p.get('condition')                                              # opcional

    products, seen = [], set()

    for query in _as_list(p['query']):
        def fetch(limit, offset, query=query):
            return client.search_products(
                query=query,
                site=s['site'],
                category=category,
                condition=condition,
                limit=limit,
                offset=offset,
            )

        fetched = 0
        try:
            for page, total in _paginate(fetch, page_size, max_offset):
                fetched += len(page)
                for product in filter_products(page, cfg):
                    if product['id'] not in seen:
                        seen.add(product['id'])

                        product['selected_attributes'] = (
                            extract_configured_attributes(product, cfg)
                        )
                        products.append(product)
                logger.info('[%s] %s buscados | %s produtos acumulados (total na API: %s)',
                            query, fetched, len(products), total)
                if _reached(len(products), max_products):
                    break
        except Exception:
            logger.exception('Erro ao paginar produtos de "%s"; seguindo com o que foi coletado', query)

        if _reached(len(products), max_products):
            break

    return products[:max_products] if max_products else products


def extract_listings(client, products, cfg):
    page_size = cfg['search']['page_size']
    max_items = cfg['search'].get('max_items')
    listings, seen = [], set()
    consulted, without_listings = 0, 0

    for product in products:
        if _reached(len(listings), max_items):
            break

        consulted += 1
        pid = product['id']

        def fetch(limit, offset, pid=pid):
            return client.listings_by_product(pid, limit=limit, offset=offset)

        try:
            for page, _ in _paginate(fetch, page_size):
                for listing in page:
                    item_id = listing.get('item_id') or listing.get('id')
                    if not item_id or item_id in seen:
                        continue
                    seen.add(item_id)
                    listing['product_id'] = pid
                    listings.append(listing)

                if _reached(len(listings), max_items):
                    break

        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else None
            if status == 404:
                without_listings += 1
                logger.info('Produto %s sem publicações', pid)
            elif status == 400:
                logger.warning('API encerrou a paginação do produto %s (HTTP 400)', pid)
            else:
                logger.exception('Erro ao buscar publicações do produto %s', pid)
        except Exception:
            logger.exception('Erro ao buscar publicações do produto %s', pid)

    listings = listings[:max_items] if max_items else listings
    logger.info('Publicações extraídas: %s | produtos consultados: %s | sem publicações: %s',
                len(listings), consulted, without_listings)

    return listings


def extract_sellers(client, seller_ids, cfg):
    multi_get = cfg['search']['multi_get']
    sellers = []

    for chunk in _chunks(sorted(seller_ids), multi_get):
        try:
            response = client.sellers(chunk)
        except Exception:
            logger.exception('Erro ao buscar lote de sellers; pulando lote')
            continue

        entries = response if isinstance(response, list) else [response]
        for entry in entries:
            if entry.get('code', 200) == 200:
                sellers.append(entry.get('body', entry))
            else:
                logger.warning('Seller ignorado (code=%s)', entry.get('code'))

    logger.info('Sellers extraídos: %s de %s ids', len(sellers), len(seller_ids))
    return sellers


def extract_conversion(client, cfg):
    from_currency, to_currency = cfg['currency']['from'], cfg['currency']['to']
    conversion = client.currency_conversions(from_currency, to_currency)

    ratio = conversion.get('ratio')
    if ratio is None:
        logger.warning('Conversão %s -> %s sem campo "ratio": %s',
                       from_currency, to_currency, conversion)
    else:
        logger.info('Conversão %s -> %s: %s', from_currency, to_currency, ratio)

    return conversion


def extract_all(client, cfg):
    products = extract_products(client, cfg)
    listings = extract_listings(client, products, cfg)

    seller_ids = {
        listing['seller_id']
        for listing in listings
        if listing.get('seller_id')
    }

    sellers = extract_sellers(client, seller_ids, cfg)
    conversion = extract_conversion(client, cfg)

    return products, listings, sellers, conversion