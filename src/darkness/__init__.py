import json
from .kzapi.crossbar import Crossbar

class KazooEnvironment:
    def __init__(self, environment) -> None:
        if isinstance(environment, str):
            environment_file = open(environment)
            environment = json.loads(environment_file.read())

        self.environment = environment

    def su_cb(self, **kwargs):
        return self.cb('superadmin', **kwargs)

    def admin_cb(self, **kwargs):
        return self.cb('admin', **kwargs)

    def user_cb(self, **kwargs):
        return self.cb('user', **kwargs)

    def cb(self, subenvironment=None, **kwargs):
        if not subenvironment:
            return Crossbar(self.environment['crossbar_url'])
        if subenvironment in self.environment['credentials']:
            return Crossbar(self.environment['crossbar_url'], **self.environment['credentials'][subenvironment], **kwargs)
        else:
            raise Exception(f"Cannot find {subenvironment} credentials for current Kazoo environment")

def create_environment(environment):
    return KazooEnvironment(environment)
