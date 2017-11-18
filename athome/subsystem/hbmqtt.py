# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

import asyncio
import logging

from hbmqtt.broker import Broker

from athome.module import SystemModule
from athome.core import Core

LOGGER = logging.getLogger(__name__)

class Subsystem(SystemModule):
    """Subsystem embedding hbmqtt broker"""

    def __init__(self, name, await_queue):
        super().__init__(name, await_queue)
        self.broker = None
        self.core = Core()

    def on_event(self, evt):
        LOGGER.debug('hbmqtt subsystem event: %s', evt)
        if not self.is_failed():
            if evt == 'athome_started':
                self.start(self.core.loop)
            elif evt == 'athome_stopping':
                self.stop()
            elif evt == 'athome_shutdown':
                self.shutdown()

    def on_start(self, loop):
        """Instantiate a fresh broker"""

        self.broker = Broker(self.config)
        self.core.emit('broker_starting')

    def after_start(self, loop):
        LOGGER.debug('after start begin')
        async def wait_broker():
            await asyncio.sleep(5)
            self.core.emit('broker_started')
        self.core.faf(wait_broker())
        LOGGER.debug('after start begin')

    async def run(self):
        """Start broker"""
        await self.broker.start()

    def on_stop(self):
        """On subsystem stop shutdown broker"""

        self.core.faf(self.broker.shutdown())
        self.broker = None

    def after_stop(self):
        self.core.emit('broker_stopping')
        
    def on_shutdown(self):
        """On subsystem shutdown shutdown broker if existing"""

        if self.broker:
            self.on_stop()
    
    def on_fail(self):
        if self.broker:
            self.broker.shutdown()

