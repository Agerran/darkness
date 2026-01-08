import pjsua2 as pj
import importlib.resources
from typing import Optional
from logging import debug

from ..events import TelephonyFuture


class PjfCall(pj.Call):
    def __init__(self, account, *args, **kwargs):
        self.player = pj.AudioMediaPlayer()
        self.answer_event: Optional[TelephonyFuture] = None
        self.collected_dtmf = []

        self.answered = False
        self.ended = False
        self.disconnect_event: Optional[TelephonyFuture] = None
        waw_file_path = 'telephony/aria.wav'
        with importlib.resources.path("darkness", waw_file_path) as wav_filename:
            print(str(wav_filename))
            self.player.createPlayer(str(wav_filename))
            self.request_headers = []
            if 'request_headers' in kwargs:
                self.request_headers = kwargs['request_headers']
            super(PjfCall, self).__init__(account, *args)

    def shutdown(self):
        self.hangup_call()
        pass

    def getCallId(self):
        ci = self.getInfo()
        return ci.callIdString

    def onCallState(self, prm):
        ci = self.getInfo()

        debug("***onCallState.callId: %s", ci.id)
        debug("***onCallState.state: %s", ci.state)
        debug("***onCallState.code: %s", ci.lastStatusCode)
        debug("***onCallState.reason: %s", ci.lastReason)
        debug("***onCallState.disconnect_fut: %s", self.disconnect_event)
        debug("***onCallState.answer_event: %s", self.answer_event)

        if ci.state == pj.PJSIP_INV_STATE_DISCONNECTED:
            self.ended = True

        if self.disconnect_event:
            if ci.state == pj.PJSIP_INV_STATE_DISCONNECTED:
                self.disconnect_event.resolve(0)

        if self.answer_event:
            if ci.state == pj.PJSIP_INV_STATE_DISCONNECTED and not self.answered:
                if not self.answer_event.done() and ci.lastStatusCode != 200:
                    self.answer_event.resolve((ci.lastStatusCode, ci.lastReason))
            elif ci.state == pj.PJSIP_INV_STATE_CONFIRMED and not self.answered:
                self.answered = True
                self.answer_event.resolve((0, 'Ok'))

        debug("***onCallState ended")

    def onDtmfDigit(self, prm):
        print("DTMF digit:", prm.digit)
        self.collected_dtmf.append(prm.digit)

        return super().onDtmfDigit(prm)

    def send_dtmf(self, digit):
        prm = pj.CallSendDtmfParam
        prm.digits = digit

        self.dialDtmf(digit)

    def await_disconnect(self, timeout):
        if not self.disconnect_event:
            self.disconnect_event = TelephonyFuture()

        if self.ended:
            self.disconnect_event.resolve(0)

        return self.disconnect_event.wait(timeout)

    def invite(self, sip_uri):
        self.answer_event = TelephonyFuture()
        self.makeCall(sip_uri, pj.CallOpParam(True))

    def hangup_call(self):
        if self.ended:
            return
        prm = pj.CallOpParam(True)
        prm.statusCode = pj.PJSIP_SC_OK
        self.hangup(prm)

    def transfer(self, number):
        prm = pj.CallOpParam(True)
        prm.statusCode = pj.PJSIP_SC_OK

        debug("*** Blind transfer")
        self.xfer(f"sip:{number}@{self.realm}", prm)

    def pickup(self):
        prm = pj.CallOpParam(True)
        prm.statusCode = pj.PJSIP_SC_OK
        self.answer(prm)

    def onCallMediaState(self, prm):
        ci = self.getInfo()
        for mi in ci.media:
            if mi.type == pj.PJMEDIA_TYPE_AUDIO and \
              (mi.status == pj.PJSUA_CALL_MEDIA_ACTIVE or \
               mi.status == pj.PJSUA_CALL_MEDIA_REMOTE_HOLD):
                m = self.getMedia(mi.index)
                am = pj.AudioMedia.typecastFromMedia(m)
                self.player.startTransmit(am)
