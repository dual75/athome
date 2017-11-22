# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

import asyncio

from athome.module import SystemModule
from athome.core import Core

class SubsystemModule(SystemModule):

    def __init__(self, name, await_queue):
        super().__init__(name, await_queue)
        self.core = Core()
        self.input_task = None
        self.input_queue = asyncio.Queue()

    def on_initialize(self):
        self.input_task = asyncio.ensure_future(self.read_events(), 
                                                loop=self.core.loop)

    async def read_events(self):
        while True:
            event = await self.input_queue.get()
            await self.on_event(event)

    async def on_event(self, evt):
        if not self.is_failed():
            if evt == 'athome_started':
                self.start(self.core.loop)
            elif evt == 'athome_stopping': 
                self.stop()
            elif evt == 'athome_shutdown':
                self.shutdown()
    
    def on_shutdown(self):
        LOGGER.debug('canceling input_task for subsystem %s', self.name)
        self.input_task.cancel()
        self.await_queue.put_nowait(self.input_task)


