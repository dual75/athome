# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

"""Hearbeat

A simple @home plugin, that publishes every 5 seconds.
"""

import logging
import asyncio
from athome.api import mqtt

LOGGER = logging.getLogger(__name__)

client = None

async def engage(loop):
    global client
    client = await mqtt.local_client()
    while client:
        await asyncio.sleep(5)
        LOGGER.info('tumping')
        await client.publish('$ATHOME/heartbeat', b'tump!')

async def shutdown():
    global client
    LOGGER.debug('shutdown!')
    if client:
        client.disconnect()
        client = None
        
    
