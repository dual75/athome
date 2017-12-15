# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

import asyncio
import logging
import contextlib

from athome import MESSAGE_EVT
from athome.system import SystemModule
from athome.core import Core

LOGGER = logging.getLogger(__name__)


class SubsystemModule(SystemModule):

    def __init__(self, name):
        super().__init__(name)
        self.core = Core()
        self.message_task = None

    def _on_initialize(self, loop, config):
        """Before 'initialize' callback"""

        super()._on_initialize(loop, config)
        self.message_task = asyncio.ensure_future(self._message_cycle(), 
                                                loop=self.core.loop)

    async def _message_cycle(self):
        with contextlib.suppress(asyncio.CancelledError):
            # messages are being processed as long as Subsystem is not 'closed'
            while not self.is_closed():
                message = await self.message_queue.get()
                await self.on_message(message)

    async def on_message(self, msg):
        LOGGER.debug('subsystem %s got msg %s', self.name, msg)
        if not self.is_failed():
            if msg.type == MESSAGE_EVT:
                if msg.value == 'athome_started':
                    self.start()
                elif msg.value == 'athome_stopping': 
                    self.stop()
                elif msg.value == 'athome_shutdown':
                    self.shutdown()

    def on_shutdown(self):
        self.message_task.cancel()
        self.core.await_queue.put_nowait(self.message_task)

