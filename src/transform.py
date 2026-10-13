import logging
import statistics

logger = logging.getLogger(__name__)

NO_WARRANTY = {'', 'sin garantía', 'sem garantia'}


def _dig(data, *keys):
    for key in keys:
        if not isinstance(data, dict):
            return None
        data = data.get(key)
    return data


def _warranty(listing):
    text = (listing.get('warranty') or '').strip()
    if not text:
        terms = {t.get('id'): t.get('value_name') for t in listing.get('sale_terms') or []}
        parts = [terms.get('WARRANTY_TYPE'), terms.get('WARRANTY_TIME')]
        text = ': '.join(part for part in parts if part)
    return text or None


def _has_warranty(text):
    return text is not None and text.casefold() not in NO_WARRANTY


def _convert_price(price, currency_id, ratio, cfg):
    if price is None:
        return None
    currency = cfg['currency']
    if currency_id == currency['to']:
        return round(price, 2)
    if currency_id == currency['from'] and ratio:
        return round(price * ratio, 2)
    return None


def _attribute(product, attribute_id):
    for attr in product.get('attributes') or []:
        if attr.get('id') == attribute_id:
            return attr.get('value_name') or None
    return None


def flag_outliers(listings, k=1.5):
    # IQR sobre price_converted.
    prices = [l['price_converted'] for l in listings if l['price_converted'] is not None]

    if len(prices) < 4:
        for listing in listings:
            listing['is_outlier'] = None if listing['price_converted'] is None else False
        return listings

    q1, _, q3 = statistics.quantiles(prices, n=4)
    iqr = q3 - q1
    low, high = q1 - k * iqr, q3 + k * iqr

    for listing in listings:
        price = listing['price_converted']
        listing['is_outlier'] = None if price is None else not (low <= price <= high)

    return listings


def transform_sellers(sellers):
    rows, seen = [], set()
    for seller in sellers:
        seller_id = seller.get('id')
        if seller_id is None or seller_id in seen:
            continue
        seen.add(seller_id)

        rows.append({
            'seller_id': seller_id,
            'nickname': seller.get('nickname'),
            'site_id': seller.get('site_id'),
            'user_type': seller.get('user_type'),
            'reputation_level_id': _dig(seller, 'seller_reputation', 'level_id'),
            'transactions_total': _dig(seller, 'seller_reputation', 'transactions', 'total'),
            'site_status': _dig(seller, 'status', 'site_status'),
        })
    return rows


def transform_products(products):
    rows, seen = [], set()
    for product in products:
        product_id = product.get('id')
        if not product_id or product_id in seen:
            continue
        seen.add(product_id)

        attributes = product.get('selected_attributes') or {}

        row = {
            'product_id': product_id,
            'name': product.get('name'),
            'parent_id': product.get('parent_id'),
            'domain_id': product.get('domain_id'),
            'brand': attributes.get('BRAND') or _attribute(product, 'BRAND'),
            'line': attributes.get('LINE') or _attribute(product, 'LINE'),
            'model': attributes.get('MODEL') or _attribute(product, 'MODEL'),
            'quality_type': product.get('quality_type'),
            'attributes': attributes,
        }

        rows.append(row)
    return rows


def transform_listings(listings, ratio, cfg):
    to_currency = cfg['currency']['to']
    rows = []

    for listing in listings:
        warranty = _warranty(listing)
        price = listing.get('price')
        price_converted = _convert_price(price, listing.get('currency_id'), ratio, cfg)

        rows.append({
            'item_id': listing.get('item_id') or listing.get('id'),
            'site_id': listing.get('site_id'),
            'product_id': listing.get('product_id'),
            'seller_id': listing.get('seller_id'),
            'accepts_mercadopago': listing.get('accepts_mercadopago'),
            'price': price,
            'currency_id': listing.get('currency_id'),
            'condition': listing.get('condition'),
            'listing_type_id': listing.get('listing_type_id'),
            'logistic_type': _dig(listing, 'shipping', 'logistic_type'),
            'warranty': warranty,
            'user_product_id': listing.get('user_product_id'),
            'total_sales': listing.get('total_sales'), # a API não informa: fica vazio
            'price_converted': price_converted,
            'converted_currency': to_currency if price_converted is not None else None,
            'is_outlier': None,
            'has_warranty': _has_warranty(warranty),
        })

    return flag_outliers(rows, cfg.get('outliers', {}).get('iqr_factor', 1.5))


def transform_all(products, listings, sellers, conversion, cfg):
    ratio = conversion.get('ratio')
    if not ratio:
        logger.warning('Taxa de conversão ausente: price_converted ficará nulo para %s',
                       cfg['currency']['from'])

    data = {
        'sellers': transform_sellers(sellers),
        'products': transform_products(products),
        'listings': transform_listings(listings, ratio, cfg),
    }

    outliers = sum(1 for row in data['listings'] if row['is_outlier'])
    logger.info('Transform: %s sellers, %s produtos, %s publicações (%s outliers)',
                len(data['sellers']), len(data['products']), len(data['listings']), outliers)
    return data
