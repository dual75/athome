# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

import os, sys
import asyncio
import logging
import concurrent

from hbmqtt.broker import Broker

from athome.module import SystemModule

LOGGER = logging.getLogger(__name__)

class Subsystem(SystemModule):
    """Subsystem embedding hbmqtt broker"""

    def on_initialize(self, config):
        """Perform subsystem initialization"""

        super().on_initialize(config)
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
        
