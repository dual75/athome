# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

import os
import sys
import asyncio
import logging
import json

from hbmqtt.broker import Broker

from athome.lib.runnersupport import RunnerSupport, runner_main
from athome.lib.lineprotocol import LineProtocol

LOGGER = logging.getLogger(__name__)


class HbmqttRunner(RunnerSupport):
    """Hbmqtt broker runner"""

    def __init__(self):
        super().__init__('hbmqtt')
        self.broker = None
       
    async def run_coro(self):
        self.broker = Broker(self.config)
        await self.broker.start()

    async def term_coro(self):
        if self.broker:
            self.broker.shutdown()
        self.broker = None


if __name__ == '__main__':
    runner = HbmqttRunner()
    runner_main(runner, True)
