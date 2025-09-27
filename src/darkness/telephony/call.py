from typing import Optional
from logging import debug

from .exception import TelephonyException
from .tf import Telephony
from ._pjf.call import PjfCall


class Call:
    def __init__(self, phone, sip_uri: Optional[str] = None, call: Optional[PjfCall] = None, *args):
        self.telephony = Telephony()
        self.telephony.addCall(self)
        self._call_id = None

        if call is None:
            self.pj_call: PjfCall = PjfCall(phone.pjf_account, *args)
        else:
            self.pj_call: PjfCall = call

        if not sip_uri:
            self.direction = 'inbound'
        else:
            self.direction = 'outbound'
            self.pj_call.invite(sip_uri)

    def hangup(self):
        """
        Ends call
        """
        debug("Telephony.Call: hanging up")
        if self.pj_call:
            self.pj_call.hangup_call()
        return self

    def pickup(self):
        debug("Pickuping")
        if self.pj_call:
            self.pj_call.pickup()

        debug("Pickuping end")
        return self

    def transfer(self, phone):
        if self.pj_call:
            self.pj_call.transfer(phone)

    def shutdown(self):
        # if self.pj_call.answer_fut:
        #    self.pj_call.answer_fut.cancel()
        # del self.pj_call.answer_fut
        debug("Telephony.Call: shutting down")

        if self.pj_call:
            self.pj_call.shutdown()
            del self.pj_call

    def ended(self) -> bool:
        if self.pj_call:
            return self.pj_call.ended
        return False

    def expect_answer(self, timeout=5.0):
        if self.pj_call and self.pj_call.answer_event:
            return self.pj_call.answer_event.wait(timeout)
        else:
            raise TelephonyException(0, 'Unknown error')

    def collect_dtmf(self):
        if self.pj_call:
            self.pj_call.collected_dtmf = []
            return self
        else:
            raise TelephonyException(0, 'Unknown error')

    def collected_dtmf(self):
        if self.pj_call:
            return self.pj_call.collected_dtmf
        else:
            raise TelephonyException(0, 'Unknown error')

    def send_dtmf(self, digit):
        if self.pj_call:
            return self.pj_call.send_dtmf(digit)
        else:
            raise TelephonyException(0, 'Unknown error')

    def expect_disconnect(self, timeout=5.0):
        if self.pj_call:
            return self.pj_call.await_disconnect(timeout)

    def call_id(self):
        if not self._call_id:
            self._call_id = self.pj_call.getCallId()
        return self._call_id

    def request_header(self, header):
        return self.pj_call.request_headers[header]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.hangup()
