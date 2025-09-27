from collections import deque
from threading import Thread, Event
from typing import Optional, Dict, List, Any, Iterator, Callable, TypeVar, Union
import websockets.asyncio.client
import websockets.sync.client
from websockets.sync.client import ClientConnection
import asyncio
import json
import uuid
import time

Message = Dict[str, Any]
MessageHandler = Callable[[Message], None]

class blackhole_ws:
    def __init__(self, url: str) -> None:
        self.url: str = url
        self.messages: List[Message] = []
        self.responses: Dict[str, Message] = {}
        self.requests_futures: Dict[str, Event] = {}
        self._socket: Optional[ClientConnection] = None
        self.subscribers: List[MessageHandler] = []

    def connect(self) -> 'blackhole_ws':
        self._socket = websockets.sync.client.connect(self.url)
        messages_collector_thread = Thread(target=self.collect_messages)
        messages_collector_thread.start()
        self.messages_collector_thread = messages_collector_thread
        return self

    def disconnect(self) -> None:
        if self._socket:
            self._socket.close()

    def collect_messages(self) -> None:
        if not self._socket:
            raise Exception("Not connected yet")
        print("Collecting messages", self)
        for message in self._socket:
            event: Message = json.loads(message)
            if 'request_id' in event:
                self.responses[event['request_id']] = event
                self.requests_futures[event['request_id']].set()
            else:
                self.messages.append(event)

            for subscriber in self.subscribers:
                subscriber(event)

    def send(self, message: str) -> None:
        if not self._socket:
            raise Exception("Not connected yet")
        self._socket.send(message)

    def receive(self) -> None:
        if not self._socket:
            raise Exception("Not connected yet")
        self._socket.recv()

    def get_response(self, request_id: str) -> Union[Message, bool]:
        if self.responses.get(request_id):
            return self.responses[request_id]
        return False

class _BlackholeSubscriptionIterator:
    def __init__(self, subscription: 'BlackholeSubscription') -> None:
        self.subscription: BlackholeSubscription = subscription
        self.messages: deque[Message] = deque([])
        self.event: Event = Event()
        self.subscription.blackhole.ws.subscribers.append(lambda m: self.onNewMessage(m))

    def __next__(self) -> Message:
        if len(self.messages) != 0:
            self.event.clear()
            return self.messages.popleft()
        else:
            self.event.wait()
            return self.__next__()

    def onNewMessage(self, message: Message) -> None:
        if 'subscription_key' in message:
            if message['subscription_key'] in self.subscription.subscription_keys:
                self.messages.append(message)
                self.event.set()

class BlackholeSubscription:
    def __init__(self, key: str, blackhole: 'Blackhole') -> None:
        self.key: str = key
        self.blackhole: Blackhole = blackhole
        self.subscription_keys: List[str] = []

    def __repr__(self) -> str:
        return f'BlackholeSubscription({self.key})'

    def __enter__(self) -> 'BlackholeSubscription':
        if not self.subscribe():
            raise Exception(f'Cannot subscribe to {self.key}')
        return self

    def __exit__(self, exc_type: Optional[type], exc_value: Optional[Exception],
                 traceback: Optional[Any]) -> None:
        self.unsubscribe()

    def subscribe(self) -> bool:
        data: Dict[str, str] = {
            'account_id': self.blackhole.crossbar.account_id,
            'binding': self.key
        }
        response = self.blackhole.request('subscribe', data)
        if not response:
            raise Exception(f'Cannot subscribe to {self.key}')
        elif response['status'] == 'error':
            raise Exception(f'Cannot subscribe to {self.key}: {response}')
        else:
            self.subscription_keys = response['data']['subscribed']
            return True

    def unsubscribe(self) -> bool:
        data: Dict[str, str] = {
            "account_id": self.blackhole.crossbar.account_id,
            "binding": self.key
        }
        response = self.blackhole.request('unsubscribe', data)
        if not response:
            raise Exception(f'Cannot subscribe to {self.key}')
        elif response['status'] == 'error':
            raise Exception(f'Cannot subscribe to {self.key}: {response}')
        else:
            return True

    def __iter__(self) -> Iterator[Message]:
        return _BlackholeSubscriptionIterator(self)

class Blackhole:
    def __init__(self, url: str, crossbar: Any) -> None:
        self.url: str = url
        self.ws: blackhole_ws = blackhole_ws(url)
        self.crossbar: Any = crossbar
        self.loop: Optional[asyncio.AbstractEventLoop] = None

    def __repr__(self) -> str:
        return f'Blackhole(url={self.url})'

    def __enter__(self) -> 'Blackhole':
        self.connect()
        return self

    def __exit__(self, exc_type: Optional[type], exc_value: Optional[Exception],
                 traceback: Optional[Any]) -> None:
        self.disconnect()

    def connect(self) -> blackhole_ws:
        return self.ws.connect()

    def disconnect(self) -> None:
        return self.ws.disconnect()

    def send(self, message: str) -> None:
        self.ws.send(message)

    def request_id(self) -> str:
        return str(uuid.uuid4())

    def request(self, action: str, data: Dict[str, Any], timeout: float = 5.0) -> Message:
        message: Dict[str, Any] = {
            'action': action,
            'data': data
        }
        return self._request(message)

    def _request(self, message: Dict[str, Any], timeout: float = 5.0) -> Message:
        request_id: str = self.request_id()
        message['request_id'] = request_id
        message['auth_token'] = self.crossbar.auth_token()
        self.ws.requests_futures[request_id] = Event()

        self.ws.send(json.dumps(message))
        self.ws.requests_futures[request_id].wait(5)

        return self.ws.responses[request_id]

    def ping(self) -> Message:
        message: Dict[str, str] = {
            "action": "ping",
            "auth_token": self.crossbar.auth_token()
        }
        return self.request(message, timeout=1.0)

    def subscription(self, key: str) -> BlackholeSubscription:
        return BlackholeSubscription(key, self)

    async def get_response(self, request_id: str) -> Optional[Message]:
        response = self.ws.get_response(request_id)
        return response

    def messages(self) -> List[Message]:
        print("Messages:", self.ws.messages)
        return self.ws.messages

    def flush_messages(self) -> None:
        print('flushing')
        self.ws.messages = []
        self.ws.responses = {}
