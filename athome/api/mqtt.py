# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

import logging

from hbmqtt.broker import Broker

from hbmqtt.client import MQTTClient
from hbmqtt.mqtt.constants import QOS_0, QOS_1, QOS_2

import athome


LOCAL_CLIENT_CONFIG = {
    'keep_alive': 30,
    'default_qos': QOS_1
}

LOGGER = logging.getLogger(__name__)

class LocalClient:

    def __init__(self, start_connected=True):
        self.client = MQTTClient(config=LOCAL_CLIENT_CONFIG)
        self.start_connected = start_connected
    
    async def __aenter__(self):
        if self.start_connected:
            await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self.client.session:
            await self.client.disconnect()

    def __getattr__(self, attr):
        return getattr(self.client, attr)

    async def connect(self):
        await self.client.connect('mqtt://localhost:1883', cleansession=True)

    async def publish(self, topic, data, qos=QOS_1):
        LOGGER.debug('publish %s(%s): %s(%s)', topic, type(topic), data, type(data))
        assert topic and isinstance(topic, str)
        assert data and isinstance(data, (bytes, str))
        if isinstance(data, bytes):
            sdata = data
        else:
            sdata = data.encode('utf-8')
        return await self.client.publish(topic, sdata, qos=qos)

    async def deliver_message(self):
        return await self.client.deliver_message()

    async def subscribe(self, *topics):
        LOGGER.debug('subscribe topics %s(%s)', topics, type(topics))
        return await self.client.subscribe(topics)


def local_client(start_connected=True):
    """Create a mqtt client connected to the local broker

    This method is a *coroutine*

    """
    return LocalClient(start_connected)
