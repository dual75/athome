# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

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

    async def on_event(self, evt):
        LOGGER.debug('hbmqtt subsystem event: %s', evt)
        if evt == 'athome_started':
            self.start()
            LOGGER.debug("hbmqtt started, waiting 5 secs.")
            await asyncio.sleep(5)
            Core().emit('broker_started')
        elif evt == 'athome_stopped':
            self.stop()
            Core().emit('broker_stopped')
        elif evt == 'athome_shutdown':
            self.shutdown()

    def on_start(self, loop):
        """Instantiate a fresh broker"""
        super().on_start(loop)
        self.broker = Broker(self.config)

    async def run(self):
        """Start broker"""
        await self.broker.start()

    def on_stop(self):
        """On subsystem stop shutdown broker"""
       
        stop_task = asyncio.ensure_future(self.broker.shutdown(), loop=self.loop)
        self.await_queue.put_nowait(stop_task)
        self.broker = None
        
    def on_shutdown(self):
        """On subsystem shutdown shutdown broker if existing"""
        if self.broker:
            self.on_stop()

