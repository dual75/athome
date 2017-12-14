# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

import asyncio
import logging
import contextlib

from athome.module import SystemModule
from athome.core import Core

LOGGER = logging.getLogger(__name__)


class SubsystemModule(SystemModule):

    def __init__(self, name):
        super().__init__(name)
        self.core = Core()
        self.event_task = None
        self.event_queue = asyncio.Queue()

    def _on_initialize(self, loop, config):
        """Before 'initialize' callback"""

        super()._on_initialize(loop, config)
        self.event_task = asyncio.ensure_future(self._event_cycle(), 
                                                loop=self.core.loop)

    async def _event_cycle(self):
        with contextlib.suppress(asyncio.CancelledError):
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
