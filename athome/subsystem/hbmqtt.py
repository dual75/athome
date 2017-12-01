    # Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

import asyncio
import logging

from hbmqtt.broker import Broker

from athome.submodule import SubsystemModule

LOGGER = logging.getLogger(__name__)

class Subsystem(SubsystemModule):
    """Subsystem embedding hbmqtt broker"""

    def __init__(self, name, await_queue):
        super().__init__(name, await_queue)
        self.broker = None

    def on_start(self):
        """Instantiate a fresh broker"""

        self.broker = Broker(self.config)
        self.core.emit('hbmqtt_starting')
        async def wait_broker():
            await asyncio.sleep(5)
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
            self.core.emit('hbmqtt_stopped')
        self.core.faf(stop_broker())
        
    def on_shutdown(self):
        """On subsystem shutdown shutdown broker if existing"""

        if self.broker:
            self.on_stop()
        super().on_shutdown()

