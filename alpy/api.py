import dateutil.parser
import os
import re
import requests
from requests.exceptions import HTTPError

ISO8601YMD = re.compile(r'\d{4}-\d{2}-\d{2}T')


class APIError(Exception):
    def __init__(self, error):
        super().__init__(error['message'])
        self._error = error

    @property
    def code(self):
        return self._error['code']


class API(object):
    def __init__(self, api_key):
        self._key = api_key
        self._base_url = os.environ.get(
            'ALPACA_API_BASE_URL', 'https://api.alpaca.markets')
        self._session = requests.Session()

    def _request(self, method, path, data=None):
        url = self._base_url + path
        headers = {
            'X-API-KEY': self._key,
        }
        opts = {
            'headers': headers,
        }
        if method.upper() == 'GET':
            opts['params'] = data
        else:
            opts['json'] = data
        resp = self._session.request(method, url, **opts)
        try:
            resp.raise_for_status()
        except HTTPError as exc:
            error = resp.json()
            if 'code' in error:
                raise APIError(error)
        if resp.text != '':
            return resp.json()
        return None

    def get(self, path, data=None):
        return self._request('GET', path, data)

    def post(self, path, data=None):
        return self._request('POST', path, data)

    def patch(self, path, data=None):
        return self._request('PATCH', path, data)

    def delete(self, path, data=None):
        return self._request('DELETE', path, data)

    def list_accounts(self):
        '''Get a list of accounts'''
        resp = self.get('/api/v1/accounts')
        return [Account(o, self) for o in resp]

    def list_assets(self, status=None, asset_class=None):
        '''Get a list of assets'''
        params = {}
        if status is not None:
            params['status'] = status
        if asset_class is not None:
            params['asset_class'] = asset_class
        resp = self.get('/api/v1/assets', params)
        return [Asset(o, self) for o in resp]

    def get_asset(self, asset_id):
        '''Get an asset'''
        resp = self.get('/api/v1/assets/{}'.format(asset_id))
        return Asset(resp, self)

    def list_quotes(self, asset_ids):
        '''Get a list of quotes'''
        if not isinstance(asset_ids, str):
            asset_ids = ','.join(asset_ids)
        params = {
            'asset_ids': asset_ids,
        }
        resp = self.get('/api/v1/quotes', params)
        return [Quote(o) for o in resp]

    def list_fundamentals(self, asset_ids):
        if not isinstance(asset_ids, str):
            asset_ids = ','.join(asset_ids)
        params = {
            'asset_ids': asset_ids,
        }
        resp = self.get('/api/v1/fundamentals', params)
        return [Fundamental(o) for o in resp]


class Entity(object):
    def __init__(self, raw):
        self._raw = raw

    def __getattr__(self, key):
        if key in self._raw:
            val = self._raw[key]
            if (isinstance(val, str) and
                    (key.endswith('_at') or key.endswith('_timestamp')) and
                    ISO8601YMD.match(val)):
                return dateutil.parser.parse(val)
            else:
                return val
        return getattr(super(), key)


class Account(Entity):

    def __init__(self, obj, api):
        super().__init__(obj)
        self._api = api
        self._account_id = obj['id']

    def _fullpath(self, path, v='1'):
        return '/api/v{}/accounts/{}{}'.format(v, self._account_id, path)

    def get(self, path, data=None):
        fullpath = self._fullpath(path)
        return self._api.get(fullpath, data)

    def post(self, path, data=None):
        fullpath = self._fullpath(path)
        return self._api.post(fullpath, data)

    def delete(self, path, data=None):
        fullpath = self._fullpath(path)
        return self._api.delete(fullpath, data)

    def list_orders(self):
        '''Get a list of orders'''
        resp = self.get('/orders')
        return [Order(o) for o in resp]

    def create_order(self, asset_id, shares, side, type, timeinforce,
                     limit_price=None, stop_price=None, client_order_id=None):
        '''Request a new order'''
        params = dict(
            asset_id=asset_id,
            shares=shares,
            side=side,
            type=type,
            timeinforce=timeinforce,
            limit_price=limit_price,
            stop_price=stop_price,
            client_order_id=client_order_id,
        )
        resp = self.post('/orders', params)
        return Order(resp)

    def get_order_by_client_order_id(self, client_order_id):
        '''Get an order by client order id'''
        resp = self.get('/orders', data={
            'client_order_id': client_order_id,
        },
        )
        return Order(resp)

    def get_order(self, order_id):
        '''Get an order'''
        resp = self.get('/orders/{}'.format(order_id))
        return Order(resp)

    def delete_order(self, order_id):
        '''Cancel an order'''
        self.delete('/orders/{}'.format(order_id))

    def list_positions(self):
        '''Get a list of open positions'''
        resp = self.get('/positions')
        return [Position(o) for o in resp]

    def get_position(self, asset_id):
        '''Get an open position'''
        resp = self.get('/positions/{}'.format(asset_id))
        return Position(resp)

    def list_dividends(self, asset_id=None, from_id=None, limit=None):
        '''Get dividends'''
        params = {}
        if from_id is not None:
            params['from_id'] = from_id
        if limit is not None:
            params['limit'] = limit
        resp = self.get('/dividends', params)
        return [Dividend(o) for o in resp]


class Asset(Entity):
    def __init__(self, raw, api):
        super().__init__(raw)
        self._api = api
        self._asset_id = raw['id']

    def get(self, path, data=None):
        fullpath = '/api/v1/assets/{}{}'.format(self._asset_id, path)
        return self._api.get(fullpath, data)

    def list_candles(self, start_dt=None, end_dt=None):
        '''Get candles'''
        params = {}
        if start_dt is not None:
            params['start_dt'] = start_dt
        if end_dt is not None:
            params['end_dt'] = end_dt
        resp = self.get('/candles', params)
        return [Candle(o) for o in resp]

    def get_quote(self):
        '''Get a quote'''
        resp = self.get('/quote')
        return Quote(resp)

    def get_fundamental(self):
        '''Get a fundamental'''
        resp = self.get('/fundamental')
        return Fundamental(resp)


class Order(Entity):
    pass


class Position(Entity):
    pass


class Dividend(Entity):
    pass


class Candle(Entity):
    pass


class Quote(Entity):
    pass


class Fundamental(Entity):
    pass