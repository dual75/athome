# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

"""Hearbeat

A simple @home plugin that simulates a switch
"""

import logging
import asyncio
from athome.api import mqtt

LOGGER = logging.getLogger(__name__)

async def engage(loop):
    client = await mqtt.local_client()
    await client.subscribe(['$ATHOME/republish/light/1', 1])
    try:
        while True:
            message = await client.deliver_message()
            LOGGER.debug('got message: %s', message.data.decode('utf-8'))
            value = int(message.data.decode('utf-8')) 
            if value:
                print('TURNED ON')
            else:
                print('TURNED OFF')
    finally:
        client.disconnect()
