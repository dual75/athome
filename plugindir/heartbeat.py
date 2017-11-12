# Copyright (c) 2017 Alessandro Duca
#
# See the file license.txt for copying permission.

"""Hearbeat

A simple @home plugin, that publishes every 5 seconds.
"""

import logging
import asyncio
import athome

LOGGER = logging.getLogger(__name__)

client = None

async def engage(loop):
    client = await athome.mqtt.local_client()
    while loop.is_running():
        await asyncio.sleep(5)
    LOGGER.info('tumping')
    await client.publish('$ATHOME/heartbeat', b'tump!')

async def shutdown():
    LOGGER.debug('shutdown!')
    if client:
        client.disconnect()
        
    
