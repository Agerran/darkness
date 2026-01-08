from typing import Optional
import pjsua2 as pj
import time
import threading
import urllib.parse
from logging import debug
import uuid

from .exception import TelephonyException
from .events import TelephonyFuture
from .tf import Telephony
from .call import Call

from ._pjf.account import PjfAccount


class Phone:
    def __init__(self, realm, login, password, **kwargs):
        debug(f"Telephony.Phone[{login}]: init")
        self.telephony = Telephony()
        self.telephony.addPhone(self)
        self.realm = realm
        self.login = login
        self.password = password
        self.otherParams = kwargs
        if 'registrar' in kwargs:
            self.registrar = kwargs['registrar']
        else:
            self.registrar = realm

        self.pjf_account = PjfAccount(self.realm, self.login, self.password, registrar=self.registrar, **kwargs)

    def __del__(self):
        print("Deleting")

    def register(self):
        self.pjf_account.register()
        if not self.pjf_account.registered:
            (code, message) = self.pjf_account.reg_error
            raise TelephonyException(code, message)

        return self.pjf_account.reg_error

    def shutdown(self):
        debug("Telephony.Phone: shutting down")
        return self.pjf_account.shutdown()

    def registered(self):
        return self.pjf_account.registered

    def start_call(self, number):
        if not self.pjf_account.registered:
            raise TelephonyException(0, "Not registered")

        sip_uri = f"sip:{number}@{self.realm}"
        self.outbound_call = Call(self, sip_uri)

        return self.outbound_call

    def expect_incoming_call(self, timeout=5.0):
        incoming_call = self.pjf_account.expect_incoming_call(timeout)
        sip_call = Call(self, call=incoming_call)
        self.inbound_call = sip_call
        return sip_call

    def expect_event(self, event_name, timeout=5.0):
        return self.pjf_account.expect_event(event_name, timeout)

    def subscribe(self, package, presence_id):
        return self.pjf_account.subscribe(package, presence_id)

    def __enter__(self):
        if not self.registered():
            print("Entering context")
            self.register()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.shutdown()
