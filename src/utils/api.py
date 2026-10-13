import logging
import os
import time
import requests

logger = logging.getLogger(__name__)


class MELIClient:
    def __init__(self, cfg):
        api = cfg['api']
        self.base = api['base_url'].rstrip('/')
        self.endpoints = api['endpoints']
        self.timeout = api.get('timeout', 10)
        self.retries = api.get('retries', 3)

        self.session = requests.Session()
        self.token = self._get_token()
        self.session.headers['Authorization'] = f'Bearer {self.token}'

    def _get_token(self):
        r = requests.post(f"{self.base}{self.endpoints['token']}", data={
            'grant_type': 'client_credentials',
            'client_id': os.environ['ML_CLIENT_ID'],
            'client_secret': os.environ['ML_CLIENT_SECRET'],
        }, timeout=self.timeout)
        r.raise_for_status()
        return r.json()['access_token']

    def _get(self, path, params=None, retries=None):
        retries = retries or self.retries
        for attempt in range(retries):
            r = self.session.get(f'{self.base}{path}', params=params, timeout=self.timeout)
            if r.status_code in (429, 500, 502, 503):
                wait = int(r.headers.get('Retry-After', 5 * (attempt + 1)))
                logger.warning('HTTP %s em %s (tentativa %s/%s); aguardando %ss',
                               r.status_code, path, attempt + 1, retries, wait)
                time.sleep(wait)
                continue
            if r.status_code >= 400:
                if r.status_code == 404:
                    logger.debug('HTTP 404 em %s', path)
                else:
                    logger.warning('HTTP %s em %s | params=%s | resposta=%s',
                                   r.status_code, path, params, r.text)
            r.raise_for_status()
            return r.json()
        raise RuntimeError(f'Falha após {retries} tentativas: {path}')

    def search_products(self, query, site, category=None, condition=None,
                        status='active', limit=50, offset=0):
        params = {
            'q': query,
            'site_id': site,
            'status': status,
            'limit': limit,
            'offset': offset,
        }
        if category:
            params['domain_id'] = category
        if condition:
            params['condition'] = condition
        return self._get(self.endpoints['products_search'], params)

    def listings_by_product(self, product_id, limit=50, offset=0):
        path = self.endpoints['product_items'].format(product_id=product_id)
        return self._get(path, {'limit': limit, 'offset': offset})

    def currency_conversions(self, from_currency, to_currency):
        return self._get(self.endpoints['currency_conversions'],
                         {'from': from_currency, 'to': to_currency})

    def sellers(self, ids):
        if isinstance(ids, (list, tuple)):
            ids_string = ','.join(map(str, ids))
        else:
            ids_string = str(ids)
        return self._get(self.endpoints['users'], {'ids': ids_string})
