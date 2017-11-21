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

    def on_event(self, evt):
        if not self.is_failed():
            if evt == 'athome_started':
                self.start(self.core.loop)
            elif evt == 'athome_stopping':
                self.stop()
            elif evt == 'athome_shutdown':
                self.shutdown()


