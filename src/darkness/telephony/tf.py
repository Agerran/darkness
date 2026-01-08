import pjsua2 as pj
import signal
import atexit
from logging import debug
import threading
from .events import EventHandler


class TelephonyException(Exception):
    def __init__(self, code, message=""):
        self.code = code
        self.message = message


class SingletoneMeta(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]

class PjTelephony(pj.Endpoint):
    def __init__(self):
        self.event_handler = EventHandler()
        super(PjTelephony, self).__init__()

    def onRejectedIncomingCall(self, prm):
        sip_message: str = prm.rdata.wholeMsg
        sip_message_lines = sip_message.split("\r\n")
        headers = {}
        for line in sip_message_lines:
            parts = line.split(':', 1)
            if len(parts) == 2:
                headers[parts[0]] = parts[1].strip()

        self.event_handler.resolve_event('rejected_call', {'data': prm.rdata.wholeMsg})

class Telephony(metaclass=SingletoneMeta):
    def __init__(self, **kwargs):
        debug("Telephony: initializing")
        # Create and initialize the library
        ep_cfg = pj.EpConfig()
        ep_cfg.logConfig.level = 4
        # ep_cfg.logConfig.level = 4 # set to 4 for reading SIP messages
        ep_cfg.medConfig.channelCount = 2
        if 'userAgent' in kwargs:
            ep_cfg.uaConfig.userAgent = kwargs['userAgent']
        ep = PjTelephony()
        ep.libCreate()
        ep.libInit(ep_cfg)

        # Create SIP transport. Error handling sample is shown
        #sipTcpTpConfig = pj.TransportConfig()
        #sipTcpTpConfig.port = 15061
        #ep.transportCreate(pj.PJSIP_TRANSPORT_TCP, sipTcpTpConfig)

        sipUdpTpConfig = pj.TransportConfig()
        sipUdpTpConfig.port = 15060
        ep.transportCreate(pj.PJSIP_TRANSPORT_UDP, sipUdpTpConfig)
        # Start the library
        ep.libStart()
        self.ep: PjTelephony = ep
        self.phones = []
        self.calls = []

        atexit.register(handle_exit)
        signal.signal(signal.SIGTERM, handle_exit)
        signal.signal(signal.SIGINT, handle_exit)

    def shutdown(self, quick=False):
        debug("Telephony: shutting down")

        for call in self.calls:
            call.shutdown()
        self.calls = []

        for phone in self.phones:
            phone.shutdown()

        self.phones = []

        if not self.ep:
            return
        if quick:
            self.ep.libDestroy(pj.PJSUA_DESTROY_NO_NETWORK)
        else:
            self.ep.libDestroy()

    def __del__(self):
        return self.shutdown(False)

    def addPhone(self, phone):
        self.phones.append(phone)

    def addCall(self, call):
        self.calls.append(call)

    def expect_rejected_call(self, timeout=5.0):
        return self.ep.event_handler.expect_event('rejected_call', timeout)


def handle_exit(*args):
    Telephony().shutdown()
