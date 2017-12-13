    # Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

import asyncio
import logging

from hbmqtt.broker import Broker

from athome.submodule import SubsystemModule
from athome.lib.management import ManagedObject

LOGGER = logging.getLogger(__name__)

class Subsystem(SubsystemModule):
    """Subsystem embedding hbmqtt broker"""

    def __init__(self, name):
        super().__init__(name)
        self.broker = None

    def on_start(self):
        """Instantiate a fresh broker"""

        self.broker = Broker(self.config)
        self.core.emit('hbmqtt_starting')
        async def wait_broker():
            await asyncio.sleep(2)
            self.started()
            self.core.emit('hbmqtt_started')
        self.core.faf(wait_broker())


    async def run(self):
        """Start broker"""

        await self.broker.start()

    def on_stop(self):
        """On subsystem stop shutdown broker"""

        self.core.emit('hbmqtt_stopping')
        async def stop_broker():
            await self.broker.shutdown()
            self.broker = None
            self.stopped()
            self.core.emit('hbmqtt_stopped')
        self.core.faf(stop_broker())
