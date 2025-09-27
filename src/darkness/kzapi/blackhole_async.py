from typing import Optional
import websockets.asyncio.client
from websockets.asyncio.client import ClientConnection
import asyncio
import json
#from .crossbar import Crossbar
import uuid
import time

class blackhole_ws:
    def __init__(self, url):
        self.url = url
        self.messages = []
        self.responses = {}
        self.requests_futures = {}
        self._socket: Optional[ClientConnection] = None

    async def connect(self):
        self._socket = await websockets.asyncio.client.connect(self.url)
        asyncio.ensure_future(self.collect_messages())
        return self

    async def disconnect(self):
        if self._socket:
            await self._socket.close()

    async def collect_messages(self):
        if not self._socket: raise Exception("Not connected yet")
        async for message in self._socket:
            event = json.loads(message)
            print("Event: ", event)
            if 'request_id' in event:
                self.responses[event['request_id']] = event
                self.requests_futures[event['request_id']].set_result(event)
            else:
                self.messages.append(event)

    async def send(self, message):
        if not self._socket: raise Exception("Not connected yet")
        await self._socket.send(message)

    async def receive(self):
        if not self._socket: raise Exception("Not connected yet")
        await self._socket.recv()

    async def get_response(self, request_id):
        await asyncio.sleep(1)
        if self.responses[request_id]:
            return self.responses[request_id]

        return False

class Blackhole:
    def __init__(self, url, crossbar):
        self.ws = blackhole_ws(url)
        self.crossbar = crossbar
        self.loop = None
    

    def get_loop(self):
        if not self.loop:
            asyncio.get_event_loop().run_until_complete(self.connect())
            return asyncio.get_event_loop()
        return self.loop

    def run_client(self):
        asyncio.ensure_future(self.__async_start_client(), loop=self.loop)
        asyncio.wait(self.connect())

    async def connect(self):
        self.loop = asyncio.get_running_loop()
        return self.ws.connect()

    async def disconnect(self):
        return await self.ws.disconnect()

    async def send(self, message):
        await self.ws.send(message)

    def request_id(self):
        return str(uuid.uuid4())

    async def request(self, message, timeout=5.0):
        if not self.loop:
            await self.connect()

        request_id = self.request_id()
        message['request_id'] = request_id
        self.ws.requests_futures[request_id] = self.get_loop().create_future()
        await self.ws.send(json.dumps(message))
        await asyncio.wait_for(self.ws.requests_futures[request_id], timeout)
        return self.ws.responses[request_id]

    def ping(self):
        message = {"action":"ping",
                   "auth_token": self.crossbar.auth_token()}

        return self.get_loop().run_until_complete(self.request(message, timeout=1.0))

    async def subscribe(self, key):
        request_id = self.request_id()
        message = {
            "action": "subscribe",
            "auth_token": self.crossbar.auth_token(),
            "request_id": request_id,
            "data": {
                "account_id": self.crossbar.account_id,
                "binding": key
            }
        }
        response = await self.request(message)
        if not response:
            return False
        elif response['status'] == 'error':
            return False
        else:
            return True

    async def get_response(self, request_id):
        response = await self.ws.get_response(request_id)
        return response

    def messages(self):
        print("Messages:", self.ws.messages)
        return self.ws.messages

    def flush_messages(self):
        print('flushing')
        self.ws.messages = []
        self.ws.responses = {}

    async def __async_start_client(self):
        await self.connect()
