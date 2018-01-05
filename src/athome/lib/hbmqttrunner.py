# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

import logging

from hbmqtt.broker import Broker

from athome.lib.runnersupport import RunnerSupport, runner_main

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
    runner_main(runner, "hbmqttrunner.log", True)
