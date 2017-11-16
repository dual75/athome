# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

import logging

from hbmqtt.broker import Broker

from athome.module import SystemModule

LOGGER = logging.getLogger(__name__)

class Subsystem(SystemModule):
    """Subsystem embedding hbmqtt broker"""

    def __init__(self, name, await_queue):
        super().__init__(name, await_queue)
        self.broker = None

    def on_start(self, loop):
        """Instantiate a fresh broker"""
        super().on_start(loop)
        self.broker = Broker(self.config)

    async def run(self):
        """Start broker"""
        await self.broker.start()

    def on_stop(self):
        """On subsystem stop shutdown broker"""
       
        self.broker.shutdown()
        self.broker = None
        
    def on_shutdown(self):
        """On subsystem shutdown shutdown broker if existing"""
        if self.broker:
            self.broker.shutdown()
        self.broker = None
