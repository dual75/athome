# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

import asyncio
import concurrent
import logging

from hbmqtt.client import ClientException, MQTTClient

from athome.module import SystemModule

LOGGER = logging.getLogger(__name__)


class Republisher(object):
    """
    """

    REPUBLISH = '$ATHOME/republish/%s'

    def __init__(self, subs, url):
        self.subs = subs
        self.url = url
        self.client = None
        self.listen_task = None
        self.pending = set()

    async def start(self):
        self.client = MQTTClient()
        await self.client.connect(self.url)
        await self.client.subscribe(self.subs.topics)
        self.listen_task = asyncio.ensure_future(
                                                 self.listen(), 
                                                 loop=self.subs.loop
                                                )

    def stop(self):
        self.listen_task.cancel()
        self.subs.await_queue.put_nowait(self.listen_task)
        self.listen_task = None
            
    async def listen(self):
        LOGGER.debug('Republisher for %s listening', self.url)
        try:
            while self.subs.running:
                message = await self.client.deliver_message()
                LOGGER.debug('Delivered message %s', message)
                await self.subs.forward(self.url, message)
                LOGGER.debug('Forwared message %s', message)
        except concurrent.futures.CancelledError:
            LOGGER.info("Republisher task canceled")
        finally:
            await self.client.disconnect()
            self.client = None

    async def forward(self, message):
        packet = message.publish_packet
        republish_topic = self.REPUBLISH % packet.variable_header.topic_name
        LOGGER.debug('Forward to topic %s' % republish_topic)
        await self.client.publish(republish_topic, packet.payload.data)                                    

class Subsystem(SystemModule):
    """MQTT Bridge subsystem"""

    def __init__(self, name, await_queue):
        super().__init__(name, await_queue)
        self.remote_urls, self.remote_clients = [], None
        self.republishers = []
        self.running = False
        self.topics = None

    def on_initialize(self, config):
        """Perform subsystem initialization"""

        super().on_initialize(config)
        self.topics = self.config['topics']
        for broker in config['brokers'].values():
            url = self._compose_url(broker)
            self.remote_urls.append(url)
    
    @staticmethod
    def _compose_url(broker):
        result = [ "%s://" % broker['protocol'] ]
        if all(k in broker for k in ('username', 'password')):
            result.append('%(username)s:%(password)s@' % broker)
        result.append(broker['host'])
        if 'port' in broker:
            result.append(":%d" % broker['port'])
        result = "".join(result)
        LOGGER.debug('Composed url %s', result)
        return result

    def on_start(self, loop):
        """Initialize or reinitializa subsystem state"""

        super().on_start(loop)
        self.running = True
        self.republishers = []

    async def run(self):
        """Start bridging activity"""

        try:
            for url in self.remote_urls:
                republisher = Republisher(self, url)
                await republisher.start()
                self.republishers.append(republisher)
        except ClientException as ex:
            LOGGER.error("Client exception: %s", ex)

    def on_stop(self):
        """On subsystem stop shutdown broker"""
        
        for republisher in self.republishers or []:
            republisher.stop()
        self.running = False
        self.republishers = None
        
    def on_shutdown(self):
        """On subsystem shutdown shutdown broker if existing"""
        
        self.on_stop()

    async def forward(self, url, message):
        """Forward a message on all republishers but original one"""
        
        LOGGER.debug('Forward message from %s', url)
        for republisher in [r for r in self.republishers if r.url != url]:
            LOGGER.debug('to %s', republisher.url)
            await republisher.forward(message)
