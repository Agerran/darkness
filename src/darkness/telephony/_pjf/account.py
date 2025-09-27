import urllib.parse
import uuid
import pjsua2 as pj
import time

from typing import Optional
from logging import debug

from .call import PjfCall

from ..events import EventHandler, EventExpector, TelephonyFuture

class PjfAccount(pj.Account):
    def __init__(self, realm, user, password, registrar="", endpoint=None, **kwargs):
        debug("Telephony.Account: __init__")
        self.realm = realm
        self.user = user
        self.password = password
        if registrar == "":
            registrar = realm

        self.reg_error = (200, "Ok")
        self.registrar = registrar
        self.registered = False
        self.incoming_call: Optional[PjfCall] = None
        self.incoming_call_event: Optional[TelephonyFuture] = None

        self.otherParams = kwargs
        self.uri = f"sip:{self.user}@{self.realm}"

        self.event_handler = EventHandler()

        super(PjfAccount, self).__init__()

    def register(self):
        debug("Telephony.Account: registering")
        self.register_event = TelephonyFuture()

        acfg = pj.AccountConfig()
        acfg.idUri = self.uri
        acfg.regConfig.registrarUri = f"sip:{self.registrar};transport=tcp"
        cred = pj.AuthCredInfo("digest", "*", self.user, 0, self.password)
        acfg.sipConfig.authCreds.append( cred )

        if 'contactParams' in self.otherParams:
            contactParamsStr = ""
            contactParams = self.otherParams['contactParams']
            for k in self.otherParams['contactParams']:
                contactParamsStr += f";{urllib.parse.quote(k)}={urllib.parse.quote(contactParams[k])}"

            acfg.regConfig.contactParams = contactParamsStr
        self.create(acfg)

        if not self.register_event.wait(5):
            self.reg_error = (0, "Timeout")

    def shutdown(self):
        if self.incoming_call_event:
            self.incoming_call_event = None
        if self.incoming_call:
            self.incoming_call = None
        super().shutdown()

    def onIncomingCall(self, prm):
        sip_message: str = prm.rdata.wholeMsg
        sip_message_lines = sip_message.split("\r\n")
        headers = {}
        for line in sip_message_lines:
            parts = line.split(':', 1)
            if len(parts) == 2:
                headers[parts[0]] = parts[1].strip()
            debug(f"SIP message: {line}")

        incoming_call = PjfCall(self, prm.callId, request_headers=headers)
        self.incoming_call = incoming_call

        prm = pj.CallOpParam(True)
        prm.statusCode = pj.PJSIP_SC_OK

        if self.incoming_call_event:
            self.incoming_call_event.resolve(self.incoming_call)

    def onMwiInfo(self, prm):
        self.event_handler.resolve_event('mwi', prm.rdata.wholeMsg)
        return super().onMwiInfo(prm)

    def expect_incoming_call(self, timeout = 5.0):
        self.incoming_call_event = TelephonyFuture()
        return self.incoming_call_event.wait(timeout)

    def pickup(self):
        prm = pj.CallOpParam(True)
        prm.statusCode = pj.PJSIP_SC_OK
        if self.incoming_call:
            self.incoming_call.answer(prm)

    def decline(self):
        prm = pj.CallOpParam(True)
        prm.statusCode = pj.PJSIP_SC_DECLINE
        if self.incoming_call:
            self.incoming_call.answer(prm)

    def delete(self):
        if self.incoming_call:
            del self.incoming_call

    def onRegState(self, prm):
        self.registered = prm.status == pj.PJ_SUCCESS
        regid = str(uuid.uuid4())
        debug(f"Telephony.Account[{self.uri}][{regid}]: onRegState code={prm.code} reason='{prm.reason}' expiration={prm.expiration}")
        self.latestRegState = prm
        if prm.status != pj.PJ_SUCCESS:
            self.reg_error = (prm.code, prm.reason)

        if self.register_event:
            self.register_event.resolve(self.reg_error)

    def expect_event(self, event, timeout=5.0):
        return self.event_handler.expect_event(event, timeout)
