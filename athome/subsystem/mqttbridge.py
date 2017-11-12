# Copyright (c) 2017 Alessandro Duca
#
# See the file license.txt for copying permission.

import asyncio
import logging
import concurrent

LOGGER = logging.getLogger(__name__)

__loop = None
config = None

async def startup(loop, config_, in_queue):
    global __loop, config
    __loop, config = loop, config_
    try:
        while True:
            try:
                msg = in_queue.get_nowait()
                if msg:
                    break   
            except asyncio.QueueEmpty:
                pass

            LOGGER.debug('Subsystem cycle')
            await asyncio.sleep(5)
    except concurrent.futures.CancelledError as ex:
        pass

async def shutdown():
    LOGGER.debug('Shutting down')


