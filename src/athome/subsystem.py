# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

import asyncio
import logging
import contextlib

from athome import Message, MESSAGE_EVT, MESSAGE_SHUTDOWN, MESSAGE_START
from athome.system import SystemModule
from athome.lib.jobs import Executor
from athome.core import Core

LOGGER = logging.getLogger(__name__)


class SubsystemModule(SystemModule):

    def __init__(self, name):
        super().__init__(name)
        self.core = Core()

    async def message_cycle(self):
        message = Message(MESSAGE_START, None)
        while message.type != MESSAGE_SHUTDOWN:
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
    
    def emit(self, evt):
        self.core.emit(evt)
