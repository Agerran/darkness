import threading

from .exception import TelephonyException

class TelephonyFuture():
    def __init__(self):
        self.result = None
        self.event = threading.Event()

    def resolve(self, result):
        self.result = result
        self.event.set()

    def done(self):
        return self.event.is_set()

    def wait(self, timeout=5.0):
        result = self.event.wait(timeout)
        if result:
            return self.result
        else:
            raise TelephonyException(0, "Timeout")


class EventHandler:
    def __init__(self):
        self.events = {}
        self.futures = {}
        
    def add_event_handler(self, event, handler):
        if not event in self.events:
            self.events[event] = []

        self.events[event].append(handler)

    def expect_event(self, event_name, timeout=5.0):
        f = TelephonyFuture()
        self.futures[event_name] = f
        return EventExpector(f, timeout)

    def resolve_event(self, event_name, event):
        if event_name in self.futures:
            self.futures[event_name].resolve(event)
    pass

class EventExpector:
    def __init__(self, future, timeout=5.0):
        self.future = future
        self.timeout = timeout
        self.value = None

    def __enter__(self):
        self.value = self.future.wait(self.timeout)
        return self

    def __exit__(self, type, value, traceback):
        pass
