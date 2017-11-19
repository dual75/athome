# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

"""Hearbeat

A simple @home plugin, that publishes every 5 seconds.
"""

import logging
import asyncio
from athome.api import mqtt
from contexlib import suppress

LOGGER = logging.getLogger(__name__)

async def engage(loop):
    global client
    client = await mqtt.local_client()
    try:
        while True:
            await asyncio.sleep(5)
            await client.publish('heartbeat', b'tump!')
    except asyncio.CancelledError:
        LOGGER.debug('heartbeat cancelled')
    finally:
        client.disconnect()
