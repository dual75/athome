# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

import asyncio
import logging
import time
import zlib

from transitions import Machine
from hbmqtt.client import ClientException, ConnectException, MQTTClient

from athome import MESSAGE_EVT
from athome.core import Core
from athome.subsystem import SubsystemModule
from athome.lib.management import ManagedObject
from athome.lib.jobs import Executor

LOGGER = logging.getLogger(__name__)


class Republisher():
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
        self.executor = Executor(self.bridge.core.loop)

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
            self.listen_task.close()
            self.listen_task = None

        # if listen didn't exit on CancelledError we try
        # to do anything to clean pending connections
        if self.client:
            async def disconnect_coro():
                await self.client.disconnect()
                self.client = None
            self.executor.execute(disconnect_coro())

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
            LOGGER.exception('can\'t connect republisher, stopping bridge')
            self.fail(ex)
        except Exception as ex:
            LOGGER.exception('exception for %s in error, stopping bridge', 
                             self.url)
            self.fail(ex)

    def _on_fail(self, exception):
        self.bridge.stop()

    async def _forward_topics(self, message):
        """Forward a message to connected broker

        This method republishes a MQTT message to the connected broker, an hash
        value of any forwarded method is kept to prevent infinite republishing.
        The hash of republished messages is deleted upon the first 
        retransimission retry.

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
        )
        return result


class Subsystem(SubsystemModule):
    """MQTT Bridge subsystem"""

    def __init__(self, name):
        super().__init__(name)
        self.broker_infos = None
        self.republishers = []
        self.broker_infos = []
        self.topics = None
        self.core = Core()

    async def on_message(self, msg):
        LOGGER.debug('hbmqttbridge msg handler: %s', msg)
        if not self.is_failed():
            if msg.type == MESSAGE_EVT:
                if msg.value == 'hbmqtt_started':
                    self.start()
                elif msg.value == 'hbmqtt_stopping':
                    self.stop()
                elif msg.value == 'athome_shutdown':
                    self.shutdown()

    def on_initialize(self):
        """Perform subsystem initialization"""

        self.republishers = []
        self.broker_infos = []
        for broker in [b for b in self.config['brokers'].values() 
                       if b['enable']
                      ]:
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
        return result

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

    def after_started(self):
        self.core.emit('mqttbridge_started')

    def on_stop(self):
        """On subsystem stop shutdown broker"""

        if self.republishers:
            for republisher in [r for r 
                    in self.republishers if not r.is_failed()]:
                republisher.stop()
            self.republishers = None
    
    def after_stopped(self):
        self.core.emit('mqttbridge_stopped')

    def on_shutdown(self):
        """On subsystem shutdown shutdown broker if existing"""

        if self.is_running():
            self.on_stop()

    async def forward(self, message):
        """Forward a message on all republishers but original one"""

        for republisher in self.republishers:
            LOGGER.debug('forward to %s', republisher.url)
            await republisher.forward(message)