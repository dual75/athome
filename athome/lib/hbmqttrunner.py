# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

import os
import sys
import asyncio
import logging
import json

from hbmqtt.broker import Broker

from athome.lib.runnersupport import RunnerSupport
from athome.lib.lineprotocol import LineProtocol

LOGGER = logging.getLogger(__name__)

class Runner(RunnerSupport):
    """Hbmqtt broker runner"""

    def __init__(self, config):
        super().__init__()
        self.broker = None
        self.config = config
       
    async def start_task(self):
        self.broker = Broker(self.config)
        await self.broker.start()

    async def stop_task(self):
        self.broker.shutdown()
        self.broker = None


def main():
    logging.basicConfig(level=logging.DEBUG)
    os.setpgid(os.getpid(), os.getpid())

    loop = asyncio.get_event_loop()
    loop.set_debug(False)
    runner = Runner(json.loads(sys.argv[1]))
    task = asyncio.ensure_future(runner.run())
    loop.run_until_complete(task)

    tasks = asyncio.Task.all_tasks()
    if tasks:
        for task in tasks:
            task.cancel()
        gather_task = asyncio.gather(*tasks, 
            loop=loop, 
            return_exceptions=True
        )
        loop.run_until_complete(gather_task)

    loop.close()
    sys.exit(0)


if __name__ == '__main__':
    main()
