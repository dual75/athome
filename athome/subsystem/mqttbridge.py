# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

import asyncio
import logging
import time
import zlib

from transitions import Machine
from hbmqtt.client import ClientException, ConnectException, MQTTClient

from athome.module import SystemModule
from athome.core import Core, Message, MESSAGE_AWAIT

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

    def __init__(self, subs, broker_info):
        self.machine = Machine(model=self,
                               states=Republisher.states,
                               transitions=Republisher.transitions,
                               initial='ready')
        self.subs = subs
        self.client = None
        self.url = broker_info['url']
        self.topics_set = set([
            topic[0] for topic in broker_info['topics'] or []
        ])
        self.topics = broker_info['topics']
        self.listen_task = None
        self.publish_set = set()
        self.publish_stamps = dict()

    def _on_start(self):
        task_list = [
             asyncio.ensure_future(self._listen(), loop=self.loop),
        ]
        if self.topics:
            task_list.append(
                asyncio.ensure_future(self._hash_cleanup(), loop=self.subs.loop)
            )
        self.run_task = asyncio.gather(*task_list, loop=self.loop)
        self.subs.core.emit('republisher_started')

    def _on_stop(self):
        """Stop this Republisher
        If there was a ConnectException the listen_task is still None

        """
        if self.listen_task:
            if not self.listen_task.done():
                self.listen_task.cancel()
            self.subs.await_queue.put_nowait(
                Message(MESSAGE_AWAIT, self.listen_task)
            )
            self.listen_task = None

    def _after_stop(self):
        LOGGER.info('bridge closed')

    async def _listen(self):
        self.client = MQTTClient()
        try:
            await self.client.connect(self.url)
            LOGGER.debug('broker connected %s', self.url)
            if self.topics:
                await self.client.subscribe(self.topics)
            LOGGER.debug('republisher for %s listening', self.url)
            while True:
                message = await self.client.deliver_message()
                LOGGER.debug("message on %s", message.publish_packet.variable_header.topic_name)
                await self.subs.forward(self.url, message)
        except asyncio.CancelledError:
            LOGGER.info("republisher task canceled")
        except:
            LOGGER.exception('exception while republishing')
        finally:
            await self.client.disconnect()
            LOGGER.info("republisher for %s disconnected", self.url)
            self.client = None

    async def forward(self, message):
        """Forward a message to connected broker

        This method republishes a MQTT message to the connected broker, an hash
        value of any forwarded method is kept to prevent infinite republishing.
        The hash of republished messages is deleted upon the first retransimission retry.

        """

        packet = message.publish_packet
        topic = packet.variable_header.topic_name
        try:
            if not self.topics:
                await self.client.publish(topic,
                                          packet.payload.data,
                                          message.qos)
            else:
                message_hash = self._hash_message(message)
                if message_hash not in self.publish_set:
                    self.publish_set.add(message_hash)
                    self.publish_stamps[message_hash] = time.time()
                else:
                    self.publish_set.remove(message_hash)
                    del self.publish_stamps[message_hash]
        except:
            LOGGER.exception('Error while publishing on %s', self.url)


    async def _hash_cleanup(self):
        while True:
            await asyncio.sleep(60, loop=self.subs.loop)
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
            if evt == 'broker_started':
                self.start(self.core.loop)
            elif evt == 'broker_stopping':
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
            self.core.emit('bridge_started')
        except ClientException as ex:
            LOGGER.error("Client exception: %s", ex)

    def on_stop(self):
        """On subsystem stop shutdown broker"""

        if self.republishers:
            for republisher in self.republishers:
                republisher.stop()
            self.republishers = None
        self.broker_infos = None

    def on_shutdown(self):
        """On subsystem shutdown shutdown broker if existing"""

        if self.is_running():
            self.on_stop()

    async def forward(self, url, message):
        """Forward a message on all republishers but original one"""

        LOGGER.debug('Forward message from %s', url)
        for republisher in self.republishers:
            LOGGER.debug('to %s', republisher.url)
            await republisher.forward(message)

    def on_fail(self):
        """on_fail placeholder"""

        if self.is_running():
            self.on_stop()
