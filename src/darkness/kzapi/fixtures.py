import pytest
import os
import json
from .kazooapi import *
import imaplib
import time
import re
import psycopg2
from ..typing import PhoneNumber
from ..telephony import Phone


def pytest_addoption(parser):
    parser.addoption("--kazoo-environment", help="Kazoo Environment")
    parser.addoption("--mail-environment", help="Mail Environment")

@pytest.fixture(scope='module')
def kazoo_environment(request):
    environment_filename = 'kazoo-environment.json'

    if request.config.getoption('kazoo_environment'):
        environment_filename = request.config.getoption('kazoo_environment')

    environment_file = open(environment_filename)
    environment = json.loads(environment_file.read())

    if "kazoo" in environment:
        environment = environment["kazoo"]

    yield environment

@pytest.fixture
def kazoo(request):
    environment_filename = 'kazoo-environment.json'

    if request.config.getoption('kazoo_environment'):
        environment_filename = request.config.getoption('kazoo_environment')

    environment_file = open(environment_filename)
    environment = json.loads(environment_file.read())

    if "kazoo" in environment:
        environment = environment["kazoo"]
        
    kazoo = Kazoo(environment)

    yield kazoo

    # event_loop.run_until_complete(kazoo.blackhole.disconnect())


def load_kazoo_environment(environment_filename):
    environment_file = open(environment_filename)
    environment = json.loads(environment_file.read())

    return environment

@pytest.fixture
def kazoo_extension(kazoo):
    cb = kazoo.crossbar
    account = cb.accounts[cb.account_id]
    extensions = []

    def _kazoo_extension(**kwargs):
        user = cb.create_user()
        device = cb.create_device(user)
        callflow = cb.create_user_callflow(user)

        extension = (user, device, callflow)
        extensions.append(extension)
        return extension

    yield _kazoo_extension

    for (user, device, callflow) in extensions:
        del account.users[user['id']]
        del account.devices[device['id']]
        del account.callflows[callflow['id']]


@pytest.fixture
def mailer(request):
    environment_filename = 'mail-environment.json'
    if (request.config.getoption('mail_environment')):
        environment_filename = request.config.getoption('mail_environment')

    environment_file = open(environment_filename)
    environment = json.loads(environment_file.read())

    if "mail" in environment:
        environment = environment["mail"]

    return Mailer(environment["host"], environment["username"], environment["password"])


class Mailer():
    def __init__(self, host, username, password):
        self.mail = imaplib.IMAP4_SSL(host)
        self.mail.login(username, password)
        self.mail.select('inbox')
        self.latest_uid = 0
        self.fetch_latest()

    def fetch_latest(self):
        typ, data = self.mail.search(None, 'UID *')
        if data != []:
            self.latest_uid = int(data[0])

        return self.latest_uid

    def wait_for_new(self, timeout=10.0):
        data = [b'']
        delay = 0.1
        latest_uid = self.latest_uid

        for i in range(int(timeout / delay)):
            self.fetch_latest()

            if latest_uid != self.latest_uid:
                break

            time.sleep(0.1)

        if latest_uid == self.latest_uid:
            raise Exception("Cannot find mail")

        typ, data = self.mail.fetch(str(self.latest_uid), '(RFC822)')

        if not data:
            raise Exception("Cannot find mail")
        if not data[0]:
            raise Exception("Cannot find mail")

        return str(data[0][1])

def wait_for_code(mailer: Mailer):
    mail = mailer.wait_for_new()

    pattern = re.compile('next code to proceed:\\\\r\\\\n\\\\r\\\\n([\\d]*)')
    match = pattern.search(str(mail))
    if match:
        code = match.group(1)
        return code
    else:
        raise Exception("Cannot find code in email")

def is_internal_number(number):
    if not is_phone_number(number):
        return False

    if len(number) > 6:
        return False

    return True

def is_phone_number(number):
    number_characters='1234567890+'
    return all(c in number_characters for c in number)

class FixtureKazooAccount():
    def __init__(self, kazoo, account_desc):

        self.kazoo = kazoo
        print(self.kazoo.environment['crossbar_url'])
        self.account_desc = account_desc

    def generate_internal_number(self):
        cb = self.admin_cb()
        callflows = cb['accounts'][cb.account_id]['callflows'].get(get_args={'paginate': 'false'})
        numbers = []
        for c in callflows:
            for n in c.numbers:
                if is_internal_number(n):
                    numbers.append(n)

        digit_numbers = [int(n) for n in numbers]
        digit_numbers.sort()
        print(digit_numbers[-1] + 1)

        return PhoneNumber(str(digit_numbers[-1] + 1))

    def generate_external_number(self):
        return PhoneNumber('+155555551000')

    def admin_cb(self):
        print(self.kazoo.environment['crossbar_url'])
        print(self.account_desc['name'])
        cb = Crossbar(self.kazoo.environment['crossbar_url'],
                        account_name=self.account_desc['name'],
                        **self.account_desc['credentials']['admin'])
        return cb

@pytest.fixture
def kazoo_account(kazoo, pytestconfig):
    if not pytestconfig.cache.get('kazoo.account', None):
        if 'account' in kazoo.environment:
            account_desc = kazoo.environment['account']
        else:
            # TODO: create account
            raise Exception("Not implemented yet")
        pytestconfig.cache.set('kazoo.account', account_desc)

    account = FixtureKazooAccount(kazoo, pytestconfig.cache.get('kazoo.account', None))
    return account


@pytest.fixture(scope='module')
def pstn_endpoint_with_number(kazoo_environment):
    return build_extension(**kazoo_environment['pstn_account'])

def peek_one_or_many(items, n=1):
    if n == 1:
        return items[0]
    else:
        return items[:n]

def build_extension(realm, username, password, number):
    device = Phone(realm, username, password)
    device.register()
    return (device, number)

@pytest.fixture(scope='module')
def extension_with_number(kazoo_environment):
    extensions = []
    for extension in kazoo_environment['extensions']:
        extensions.append(build_extension(**extension))

    return lambda n=1: peek_one_or_many(extensions, n)

@pytest.fixture(scope='module')
def inbound_number(kazoo_environment):
    return kazoo_environment['reachable_number']



@pytest.fixture
def psql():
    def psql_(system_configs):
        # Define connection parameters
        hostname = system_configs['hostname']  # This is usually the default; change as necessary.
        database = system_configs['database_name']
        username = system_configs['username']
        password = system_configs['password']

        # Establish the connection
        conn = None
        try:
            conn = psycopg2.connect(
                dbname=database,
                user=username,
                password=password,
                host=hostname
            )
            print("Connection successful!")
        except Exception as e:
            print(f"An error occurred: {e}")

        return conn

    yield psql_

