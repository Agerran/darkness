from .crossbar import Crossbar
from .blackhole import Blackhole
from .sup import Sup
import secrets
import json

def gen_string(len=12):
    return secrets.token_hex(len)

def load_kazoo_environment(environment_filename):
    environment_file = open(environment_filename)
    environment = json.loads(environment_file.read())

    return environment

class Kazoo:
    def __init__(self, environment, **kwargs):
        self.environment = environment
        self.crossbar_anonymous = Crossbar(environment['crossbar_url'])
        self.crossbar = Crossbar(environment['crossbar_url'])
        self.crossbar.set_credentials(self.environment['credentials']['admin'])
        self.cb = self.crossbar
        self.cb_admin = self.crossbar
        #self.set_access_level('admin')

        self.sucb = Crossbar(environment['crossbar_url'])
        self.sucb.set_credentials(self.environment['credentials']['superadmin'])
        self.cb_superadmin = self.sucb
        #self.sucb.make_auth_request()

        self.sup = Sup(environment['sup'])
        print(self.environment)

        self.cb_users = {}

        self.blackhole = Blackhole(environment['blackhole_url'], self.crossbar)

    def __getattr__(self, key):
        if key == 'account_id':
            return self.cb.account_id

    def cb_user(self, user_id):
        if user_id in self.cb_users:
            pass
        elif user_id in self.environment['credentials']['user']:
            self.cb_users[user_id] = Crossbar(self.environment['crossbar_url'])
            self.cb_users[user_id].set_credentials(self.environment['credentials']['user'][user_id])
        else:
            raise Exception('Unknown user_id', user_id, self.environment)

        return self.cb_users[user_id]

    def system_configs(self, group: str, data: None | dict = None) -> dict:
        if not data:
            return self.sucb['system_configs'][group].data
        else:
            return self.sucb['system_configs'][group].post({'default': data})

    def set_access_level(self, level):
        self.crossbar.set_credentials(self.environment['credentials'][level])
        self.crossbar.make_auth_request()

    async def disconnect(self):
        await self.blackhole.disconnect()

    def __enter__(self):
    #    if not self.registered():
    #        self.register()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass


    pass

