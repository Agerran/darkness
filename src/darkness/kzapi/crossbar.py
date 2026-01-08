import requests
import hashlib
from datetime import datetime
from typing import Optional, get_args
from munch import Munch

from urllib.parse import urlencode
# from urllib.parse import urlencode # python3
from collections import OrderedDict

UNIX_EPOCH_IN_GREGORIAN = 62167219200
def to_gregorian(timestamp):
    return timestamp + UNIX_EPOCH_IN_GREGORIAN

def now_gregorian():
    return to_gregorian(int(datetime.timestamp(datetime.now())))


def calculate_credentials(username, password):
    return hashlib.md5(bytes(username + ':' + password, 'utf-8')).hexdigest()

class CrossbarError(Exception):
    def __init__(self, url, code, message, data):
        self.url = url
        self.code = code
        self.message = message
        self.data = data

class _CrossbarElementFactory:
    @staticmethod
    def create(executor, path_parts, **kwargs):
        return CrossbarElement(executor, path_parts, **kwargs)

class _CrossbarIterator:
    def __init__(self, crossbar_el):
        self.crossbar_el = crossbar_el
        self.next_start_key: bool | str = True
        self.iteration_id = 0
        self.ids = []

    def __next__(self):
        if self.iteration_id >= len(self.ids):
            if self.next_start_key != False:
                self.__load_list()
            else:
                raise StopIteration

        if self.iteration_id >= len(self.ids):
            raise StopIteration  # signals "the end"

        item = self.ids[self.iteration_id]

        self.iteration_id += 1
        return item

    def __load_list(self):
        if self.next_start_key == False:
            return

        (ids, next_start_key) = self.crossbar_el._load_ids_list(self.next_start_key)

        self.next_start_key = next_start_key

        self.ids = self.ids + ids

        return ids

class CrossbarElement:
    def __init__(self, executor, path_parts, data={}, **kwargs):
        object.__setattr__(self, 'data', data)
        object.__setattr__(self, 'executor', executor)
        object.__setattr__(self, 'path_parts', path_parts)
        object.__setattr__(self, 'cached', {})
        object.__setattr__(self, 'fetched', data != {})
        object.__setattr__(self, 'get_args', {})
        object.__setattr__(self, 'kwargs', kwargs)

    def save(self, **kwargs):
        self._maybe_fetch()
        self.executor.api_request(self.path_parts, method='post', data=self.data, **kwargs)

    def create(self, data, **kwargs):
        result = self.executor.request(self.path_parts, method='put', data=data, **kwargs)
        id = result['data']['id']
        element = CrossbarElement(self.executor, self.path_parts + [id], data=result['data'])
        self.cached[id] = element
        return element

    def get(self, get_args=None, **kwargs):
        return self._request(get_args=get_args, **kwargs)

    def post(self, data, **kwargs):
        return self._request(method='post', data=data, **kwargs)

    def put(self, data, **kwargs):
        return self._request(method='put', data=data, **kwargs)

    def _request(self, method='get', data=None, get_args=None, **kwargs):
        if not get_args:
            get_args = self.get_args
        return self.executor.api_request(self.path_parts, method=method, data=data, get_args=get_args, **kwargs)

    def request(self, **kwargs):
        return self.executor.request(self.path_parts, **kwargs)

    def clear_cache(self):
        self.cached = {}

    def with_get_args(self, get_args):
        el = CrossbarElement(self.executor, self.path_parts)
        el.get_args = get_args
        return el

    def __getitem__(self, key):
        if not key in self.cached:
            try:
                item = _CrossbarElementFactory.create(self.executor, self.path_parts + [key])
                self.cached[key] = item
            except CrossbarError as ce:
                if ce.code == 404:
                    raise KeyError()
                else:
                    raise ce

        return self.cached[key]

    def __delitem__(self, key):
        result = self.executor.request(self.path_parts + [key], method='delete')
        if key in self.cached:
            del self.cached[key]

    def _maybe_fetch(self):
        # print("MAYBEFETCH", self.path_parts)
        if not self.fetched:
            data = self.executor.api_request(self.path_parts)
            self.fetched = True
            self.data = data

    def _load_ids_list(self, start_key: bool | str = False):
        get_args = dict(self.get_args)
        url = '/'.join(self.path_parts)
        if isinstance(start_key, str):
            get_args['start_key'] = start_key
#            url += f'?start_key={start_key}'

        result = self.executor.request(url, get_args=get_args)

        ids = []
        for llist_item in result['data']:
            if 'id' in llist_item:
                ids.append(llist_item['id'])
            else:
                ids.append(llist_item)

        next_start_key = False
        if 'next_start_key' in result:
            next_start_key = result['next_start_key']

        return (ids, next_start_key)

    def __getattribute__(self, key):
        if key == 'data':
            self._maybe_fetch()
        return object.__getattribute__(self, key)

    def __getattr__(self, key):
        self._maybe_fetch()
        return self.data.get(key)

    def __setattr__(self, key, value):
        if key in self.__dict__.keys():
            object.__setattr__(self, key, value)
        else:
            self._maybe_fetch()
            self.data[key] = value

    def __delattr__(self, key):
        self._maybe_fetch()
        if key in self.data.keys():
            del self.data[key]

    def __dir__(self):
        return dir(self)

    def __iter__(self):
        return _CrossbarIterator(self)

class Crossbar:
    def __init__(self, url, path_parts=[], user=None, password=None, account_name=None, version='v2', auto_auth=False, account_id=None):
        self.url = url
        self.auth_user = user
        self.auth_password = password
        self.account_name = account_name
        self._version = version
        self._auth_token = ''
        self._account_id: Optional[bool] = account_id
        self.user_id: Optional[bool] = None
        self.cached = {}
        self.auto_auth = auto_auth
        self.path_parts = path_parts

    def __getattr__(self, key):
        if key == 'account_id':
            if not self._account_id:
                self.make_auth_request()
            return self._account_id

        # Could be set by auth_request
        if key in self.__dict__:
            return self.__dict__[key]

        raise Exception(f'Unknown key: {key}')

    def __getitem__(self, key):
        if not key in self.cached:
            try:
                item = _CrossbarElementFactory.create(self, self.path_parts + [key])
                self.cached[key] = item
            except CrossbarError as ce:
                if ce.code == 404:
                    raise KeyError()
                else:
                    raise ce

        return self.cached[key]

    def __enter__(self):
        if self.auth_user and self.auth_password and self.account_name:
            self.make_auth_request()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass

    def set_credentials(self, credentials):
        self.auth_user = credentials['username']
        self.auth_password = credentials['password']
        self.account_name = credentials['account']

    def auth_token(self):
        if not self._account_id:
            self.make_auth_request()

        return self._auth_token

    def add_get_args(self, get_args):
        self.get_args = get_args
        return self

    def finish_init(self, account_id, user_id):
        self._auth_account_id = account_id
        if self._account_id is None:
            self._account_id = account_id
        self.user_id = user_id

    def calculate_credentials(self):
        if not self.auth_user or not self.auth_password:
            raise(Exception('Credentials required'))
        return calculate_credentials(self.auth_user, self.auth_password)

    def authenticate(self):
        return self.make_auth_request()

    def make_auth_request(self, retresult=False):
        print("MAKING AUTH REQUEST",self.auth_user, self.auth_password, self.account_name)
        credentials = self.calculate_credentials()

        (r, rdata) = self._request('user_auth', version='v2', data={'credentials': credentials, 'account_name': self.account_name}, method='put')

        if isinstance(rdata, dict):
            self._auth_token = rdata['auth_token']
            self.finish_init(rdata['data']['account_id'], rdata['data']['owner_id'])
        else:
            raise(CrossbarError('user_auth', r.status_code, 'Unknown return data', r))

        return r

    def _request(self, url, **kwargs):
        return self.internal_request(url, **kwargs)

    def internal_request(self, url, data={}, method='get', headers=None, anonymous=False, version=None, timeout=30):
        if not version:
            version = self._version
        full_url = f'{self.url}/{version}/{url}'
        full_data = None
        if data:
            full_data = {"data": data}
        if not headers:
            headers = {}

        if (self._auth_token != '' and not anonymous):
            headers['X-AUTH-TOKEN'] = self._auth_token

        r = requests.request(method, full_url, json=full_data, headers=headers, timeout=timeout)

        # print(url, data, r.status_code)
        
        if (r.status_code == 401):
            raise CrossbarError(url, 401, "Auth required", r)

        if (r.status_code // 100 != 2):
            message = 'Unknown Error'
            data = None
            try:
                response = r.json()
                data = response['data']
                message = response['message']
            except:
                pass

            raise CrossbarError(url, r.status_code, message, r)

        rdata = r
        if (r.headers['Content-Type'] == 'application/json'):
            rdata = r.json()
        else:
            rdata = r.content

        return (r, rdata)


    def request(self, url, data={}, repeat=3, method='get', get_args=False, retrequest=False, headers={}, anonymous=False, **kwargs):
        if isinstance(url, list):
            url = '/'.join(url)

        if get_args:
            query_string = urlencode(OrderedDict(get_args))
            url += '?' + query_string

        if (repeat == 0):
            raise CrossbarError(url, 500, 'Retry limit reached', data)

        try:
            (r, rdata) = self._request(url, data=data, method=method, headers=headers, anonymous=anonymous, **kwargs)
            if retrequest:
                return r
            else:
                return rdata

        except CrossbarError as ce:
            if not self.auth_user and not self.auth_password and not self.account_name:
                anonymous = True
            if ce.code == 401 and repeat > 1 and not anonymous:
                self.make_auth_request()
                return self.request(url, data,  repeat-1, method=method, get_args=get_args, retrequest=retrequest, headers=headers,anonymous=anonymous,**kwargs)
            else:
                r = ce.data
                try:
                    response = r.json()
                    data = response['data']
                    message = response['message']
                except:
                    pass

                raise CrossbarError(url, r.status_code, ce.message, data)

    def api_request(self, url, *args, **kwargs):
        result = self.request(url, *args, **kwargs)
        retrequest = 'retrequest' in kwargs and kwargs['retrequest']
        if retrequest:
            return result
        if not isinstance(result, dict):
            raise CrossbarError(url, 500, "Unknown error", result)
        return Munch.fromDict(result["data"])
