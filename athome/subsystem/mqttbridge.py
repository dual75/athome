# Copyright (c) 2017 Alessandro Duca
#
# See the file license.txt for copying permission.

import asyncio
import logging
import concurrent

LOGGER = logging.getLogger(__name__)

_loop = None
_config = None

def initialize(config):
    """Perform subsystem initialization"""

    global _broker, _config
    _config = config


async def run(loop, in_queue):
    global _loop, config
    _loop = loop
    try:
        while True:
            msg = await in_queue.get()
            if msg == 'start':
                LOGGER.debug('Subsystem {} started'.format(__name__))
            if msg == 'stop':
                pass
            elif msg == 'restart':
                pass
            elif msg == 'shutdown':
                await shutdown()
                break
    except concurrent.futures.CancelledError as ex:
        LOGGER.error('Caught CancelledError in {}'.format(__name__))


async def shutdown():
    LOGGER.debug('Shutting down')


