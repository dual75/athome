# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

import asyncio
import concurrent
import logging

from hbmqtt.client import ClientException, ConnectException, MQTTClient

from athome.module import SystemModule
from athome.core import Core, Message, MESSAGE_AWAIT

LOGGER = logging.getLogger(__name__)


class Republisher(object):
    """
    """

    REPUBLISH = 'athome/bridged/%s'

    def __init__(self, subs, url, await_queue):
        self.subs = subs
        self.url = url
        self.client = None
        self.listen_task = None
        self.await_queue = await_queue

    async def start(self):
        self.client = MQTTClient()
        try:
            await self.client.connect(self.url)
            await self.client.subscribe(self.subs.topics)
            self.listen_task = asyncio.ensure_future(
                                                 self.listen(), 
                                                 loop=self.subs.loop
                                                )
            self.subs.core.emit('republisher_started')
        except ConnectException as ex:
            LOGGER.error("ClientException while trying to connect Republisher")
            self.subs.close()

    def stop(self):
        """Stop this Republisher
        If there was a ConnectException the listen_task is still None
        
        """
        if self.listen_task:
            if not self.listen_task.done():
                self.listen_task.cancel()
            self.await_queue.put_nowait(Message(MESSAGE_AWAIT,
                                                self.listen_task)
                                       )
            self.listen_task = None

    def after_stop(self):
        LOGGER.info('bridge closed')
            
    async def listen(self):
        LOGGER.debug('Republisher for %s listening', self.url)
        try:
            while self.subs.running:
                message = await self.client.deliver_message()
                await self.subs.forward(self.url, message)
        except asyncio.CancelledError:
            LOGGER.info("Republisher task canceled")
        finally:
            await self.client.disconnect()
            self.client = None

    async def forward(self, message):
        packet = message.publish_packet
        republish_topic = self.REPUBLISH % packet.variable_header.topic_name
        LOGGER.debug('Forward to topic %s' % republish_topic)
        try:
            await self.client.publish(republish_topic, 
                                      packet.payload.data, 
                                      message.qos)
        except:
            LOGGER.exception('Error while publishing on %s', self.url)


class Subsystem(SystemModule):
    """MQTT Bridge subsystem"""

    def __init__(self, name, await_queue):
        super().__init__(name, await_queue)
        self.remote_urls, self.remote_clients = [], None
        self.republishers = []
        self.running = False
        self.topics = None
        self.core = Core()

    def on_event(self, evt):
        LOGGER.debug('hbmqttbridge subsystem event: %s', evt)
        if not self.is_failed():
            if evt == 'broker_started':
                self.start(self.core.loop)
            elif evt == 'broker_stopping':
                self.stop()
            elif evt == 'athome_shutdown':
                self.shutdown()

    def on_initialize(self):
        """Perform subsystem initialization"""

        self.topics = self.config['topics']
        for broker in self.config['brokers'].values():
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
        """Initialize or reinitialize subsystem state"""

        self.running = True
        self.republishers = []

    async def run(self):
        """Start bridging activity"""

        try:
            for url in self.remote_urls:
                republisher = Republisher(self, url, self.await_queue)
                await republisher.start()
                self.republishers.append(republisher)
            self.core.emit('bridge_started')
        except ClientException as ex:
            LOGGER.error("Client exception: %s", ex)

    def on_stop(self):
        """On subsystem stop shutdown broker"""
        
        if self.republishers:
            for republisher in self.republishers:
                republisher.stop()
            self.republishers = None
        self.running = False
        
    def on_shutdown(self):
        """On subsystem shutdown shutdown broker if existing"""
        
        if self.is_running():
            self.on_stop()

    async def forward(self, url, message):
        """Forward a message on all republishers but original one"""
        
        LOGGER.debug('Forward message from %s', url)
        for republisher in [r for r in self.republishers if r.url != url]:
            LOGGER.debug('to %s', republisher.url)
            await republisher.forward(message)
       
    def on_fail(self):
        """on_fail placeholder"""

        if self.is_running():
            self.on_stop()

