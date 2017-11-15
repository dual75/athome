# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

import asyncio
import concurrent
import logging
import os
import sys

from hbmqtt.client import ClientException, MQTTClient
from hbmqtt.mqtt.constants import QOS_1, QOS_2

from athome.api import mqtt
from athome.module import SystemModule

LOGGER = logging.getLogger(__name__)


class Republisher(object):
    def __init__(self, subs, url):
        self.subs = subs
        self.url = url
        self.client = None
        self.subscribe_task = None

    async def start(self):
        self.client = MQTTClient()
        await self.client.connect(self.url)
        await self.client.subscribe(self.topics)
        self.subscribe_task = loop.ensure_future(self.listen())

    def stop(self):
        self.subscribe_task.cancel()
        try:
            self.subscribe_task.exception()
        finally:
            self.client.disconnect()

    async def listen(self):
        while self.subs.running:
            message = await self.client.deliver_message()
            self.subs.forward(self.url, message)

    async def forward(self, message):
        packet = message.publish_packet
        self.client.publish(packet.variable_header.topic_name,
                                packet.payload.data)                                    


class Subsystem(SystemModule):
    """MQTT Bridge subsystem"""

    def on_initialize(self, config):
        """Perform subsystem initialization"""

        super().on_initialize(config)
        self.topics = self.config['topics']
        self.remote_urls, self.remote_clients = [], None
        for broker in config['brokers'].values():
            url = self._compose_url(broker)
            self.remote_urls.append(url)
        self.republishers = []
    
    def _compose_url(self, broker):
        result = [ "{}://".format(broker['protocol']) ]
        if all(k in broker for k in ('username', 'password')):
            result.append('{}:{}@'.format(broker['username'], broker['password']))
        result.append("{}:{}".format(broker['host'], broker['port']))
        return "".join(result)
            
    def on_start(self, loop):
        """Initialize or reinitializa subsystem state"""

        super().on_start(loop)
        self.running = True
        self.republishers = []

    async def run(self):
        """Start bridging activity"""

        try:
            local_client = await mqtt.local_client()
            remote_clients = {'local': local_client}
            for url in self.remote_urls:
                client = MQTTClient()
                remote_clients[url] = client
                LOGGER.debug('Connect to %s' % url)
                await client.connect(url)
            tasks = []
            for url, client in remote_clients.items():
                republisher = Republisher(self, url)
                self.republishers.append(republisher)
                await republisher.start()
                tasks.append(republisher.run_task)
            await asyncio.gather(tasks)
                
        except ClientException as ce:
            LOGGER.error("Client exception: %s" % ce)
          

    def on_stop(self):
        """On subsystem stop shutdown broker"""
        
        self.running = False
        for republisher in self.republishers or []:
            republisher.stop()
        self.republishers = None
        
    def on_shutdown(self):
        """On subsystem shutdown shutdown broker if existing"""
        
        self.on_stop()

    async def forward(self, url, message):
        """Forward a message on all republishers but original one"""
        
        for republisher in self.republishers:
            if url != republisher.url:
                await republisher.forward(message)
