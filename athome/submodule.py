# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

import asyncio
import logging

from athome import Message, MESSAGE_AWAIT
from athome.module import SystemModule
from athome.core import Core

LOGGER = logging.getLogger(__name__)


class SubsystemModule(SystemModule):

    def __init__(self, name, await_queue):
        super().__init__(name, await_queue)
        self.core = Core()
        self.event_task = None
        self.event_queue = asyncio.Queue()

    def _on_initialize(self, loop, config):
        """Before 'initialize' callback"""

        super()._on_initialize(loop, config)
        self.event_task = asyncio.ensure_future(self._read_events(), 
                                                loop=self.core.loop)

    async def _read_events(self):
        while True:
            event = await self.event_queue.get()
            await self.on_event(event)

    async def on_event(self, evt):
        LOGGER.debug('subsystem %s got event %s', self.name, evt)
        if not self.is_failed():
            if evt == 'athome_started':
                self.start()
            elif evt == 'athome_stopping': 
                self.stop()
            elif evt == 'athome_shutdown':
                self.shutdown()
    
    def on_shutdown(self):
        LOGGER.debug('canceling input_task for subsystem %s', self.name)
        self.event_task.cancel()
        self.await_queue.put_nowait(Message(MESSAGE_AWAIT, self.event_task))

