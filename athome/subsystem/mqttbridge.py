# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

import asyncio
import logging
import time
import zlib

from transitions import Machine
from hbmqtt.client import ClientException, ConnectException, MQTTClient

from athome.core import Core
from athome.module import SystemModule
from athome import Message, MESSAGE_AWAIT

LOGGER = logging.getLogger(__name__)


class Republisher(object):
    """
    """

    states = [
        'ready',
        'running',
        'failed'
    ]

    transitions = [
        {
            'trigger': 'start',
            'source': 'ready',
            'dest': 'running',
            'before': ['_on_start']
        },
        {
            'trigger': 'stop',
            'source': 'running',
            'dest': 'ready',
            'before': ['_on_stop'],
            'after': ['_after_stop']
        },
        {
            'trigger': 'fail',
            'source': ['loaded', 'ready', 'running'],
            'dest':'failed',
            'before': ['_on_fail']
        }
    ]

    def __init__(self, bridge, broker_info):
        self.machine = Machine(model=self,
                               states=Republisher.states,
                               transitions=Republisher.transitions,
                               initial='ready')
        self.bridge = bridge
        self.client = None
        self.url = broker_info['url']
        self.topics = broker_info['topics']
        self.listen_task = None
        self.publish_set = set()
        self.publish_stamps = dict()

    def _on_start(self):
        """Start this republisher

        Start the cleanup task if the Republisher subscribes any topic.

        """

        task_list = [
            asyncio.ensure_future(self._listen(), loop=self.bridge.loop),
        ]
        if self.topics:
            task_list.append(
                asyncio.ensure_future(
                    self._hash_cleanup(), loop=self.bridge.loop)
            )
            self.forward = self._forward_topics
        self.run_task = asyncio.gather(*task_list, loop=self.bridge.loop)
        self.bridge.core.emit('republisher_started')

    def _on_stop(self):
        """Stop this Republisher
        If there was a ConnectException the listen_task is still None

        """

        if self.listen_task:
            if not self.listen_task.done():
                self.listen_task.cancel()
            self.bridge.await_queue.put_nowait(
                Message(MESSAGE_AWAIT, self.listen_task)
            )
            self.listen_task = None

        # if listen didn't exit on CancelledError we try
        # to do anything to clean pending connections
        if self.client:
            async def disconnect_coro():
                await self.client.disconnect()
                self.client = None
            self.bridge.core.faf(disconnect_coro())

    def _after_stop(self):
        LOGGER.info('republisher for %s closed', self.url)

    async def _listen(self):
        LOGGER.debug('republisher for %s starting', self.url)
        try:
            self.client = MQTTClient()
            await self.client.connect(self.url)
            if self.topics:
                await self.client.subscribe(self.topics)
                LOGGER.debug('republisher for %s listening', self.url)
                while True:
                    message = await self.client.deliver_message()
                    LOGGER.debug("message on %s",
                             message.publish_packet.variable_header.topic_name)
                    await self.bridge.forward(message)
        except asyncio.CancelledError:
            # self.client its unlilke to be None but we check anyway
            if self.client:
                await self.client.disconnect()
                self.client = None
            LOGGER.debug("republisher list_task for %s canceled", self.url)
        except ConnectException as ex:
            LOGGER.exception('can\'t connect republisher, now stopping mqttbridge')
            self.fail(ex)
        except Exception as ex:
            LOGGER.exception('exception for %s in error, now stopping bridge', self.url)
            self.fail(ex)

    def _on_fail(self, exception):
        self.bridge.stop()

    async def _forward_topics(self, message):
        """Forward a message to connected broker

        This method republishes a MQTT message to the connected broker, an hash
        value of any forwarded method is kept to prevent infinite republishing.
        The hash of republished messages is deleted upon the first retransimission retry.

        """

        packet = message.publish_packet
        topic = packet.variable_header.topic_name
        message_hash = self._hash_message(message)
        if message_hash not in self.publish_set:
            self.publish_set.add(message_hash)
            self.publish_stamps[message_hash] = time.time()
            await self.client.publish(topic,
                                  packet.payload.data,
                                  message.qos
                                  )         
        else:
            self.publish_set.remove(message_hash)
            del self.publish_stamps[message_hash]

    async def _forward_notopics(self, message):
        """Forward a message to connected broker

        This method republishes a MQTT message to the connected broker, the 
        connected client doesn't subscribe to any topic so we don't need any 
        retransmission prevention policy.

        """
        packet = message.publish_packet
        topic = packet.variable_header.topic_name
        await self.client.publish(topic,
                                  packet.payload.data,
                                  message.qos
                                  )

    forward = _forward_notopics

    async def _hash_cleanup(self):
        while True:
            await asyncio.sleep(300, loop=self.bridge.loop)
            now = time.time()
            self.publish_set = self.publish_set - {
                hash_
                for hash_ in self.publish_set
                if now - self.publish_stamps[hash_] > 60000
            }
            self.publish_stamps = {
                hash_: self.publish_stamps[hash_]
                for hash_ in self.publish_stamps
                if hash_ in self.publish_set
            }

    @staticmethod
    def _hash_message(message):
        packet = message.publish_packet
        result = zlib.crc32(
            packet.variable_header.topic_name.encode('utf-8')
            + packet.payload.data
            + bytes(message.qos)
        )
        return result


class Subsystem(SystemModule):
    """MQTT Bridge subsystem"""

    def __init__(self, name, await_queue):
        super().__init__(name, await_queue)
        self.broker_infos = None
        self.republishers = []
        self.broker_infos = []
        self.topics = None
        self.core = Core()

    def on_event(self, evt):
        LOGGER.debug('hbmqttbridge event handler: %s', evt)
        if not self.is_failed():
            if evt == 'hbmqtt_started':
                self.start(self.core.loop)
            elif evt == 'hbmqtt_stopping':
                self.stop()
            elif evt == 'athome_shutdown':
                self.shutdown()

    def on_initialize(self):
        """Perform subsystem initialization"""

        self.broker_infos = []
        for broker in self.config['brokers'].values():
            url = self._compose_url(broker)
            self.broker_infos.append({
                'url': url,
                'topics': broker['topics'] if 'topics' in broker else None
            })

    @staticmethod
    def _compose_url(broker):
        result = ["%s://" % broker['protocol']]
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
        """Perform bridging activity"""

        try:
            for broker in self.broker_infos:
                republisher = Republisher(self, broker)
                republisher.start()
                self.republishers.append(republisher)
            self.core.emit('mqttbridge_started')
        except ClientException as ex:
            LOGGER.error("Client exception: %s", ex)

    def on_stop(self):
        """On subsystem stop shutdown broker"""

        if self.republishers:
            for republisher in [r for r in self.republishers if not r.is_failed()]:
                republisher.stop()
            self.republishers = None
    
    def after_stop(self):
        self.core.emit('mqttbridge_stopped')

    def on_shutdown(self):
        """On subsystem shutdown shutdown broker if existing"""

        if self.is_running():
            self.on_stop()

    async def forward(self, message):
        """Forward a message on all republishers but original one"""

        for republisher in self.republishers:
            LOGGER.debug('to %s', republisher.url)
            await republisher.forward(message)

    def on_fail(self):
        """on_fail placeholder"""

        if self.is_running():
            self.on_stop()
