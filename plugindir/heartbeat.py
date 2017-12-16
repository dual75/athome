# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

"""Hearbeat

A simple @home plugin, that publishes every 5 seconds.
"""

import logging
import asyncio
import hbmqtt.client

from athome.api import mqtt
from contextlib import suppress

LOGGER = logging.getLogger(__name__)

async def task_heartbeat(loop):
    async with mqtt.local_client() as client:
        await asyncio.sleep(5)
        await client.publish('heartbeat', b'tump!')

