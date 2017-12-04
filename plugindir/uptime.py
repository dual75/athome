# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

"""Hearbeat

A simple @home plugin that simulates a switch
"""

import logging
import asyncio
import subprocess
from athome.api import mqtt

LOGGER = logging.getLogger(__name__)


async def engage(loop):
    LOGGER.info("Light plugin engage")
    client = await mqtt.local_client()
    await client.subscribe((('system/request', 1),))
    try:
        while True:
            message = await client.deliver_message()
            LOGGER.error('got message: %s', message.data.decode('utf-8'))
            try:
                value = int(message.data.decode('utf-8')) 
                completed = subprocess.run(value, stdout=subprocess.PIPE)
                await client.publish('subsystem/output', completed.stdout, 1)
            except:
                LOGGER.exception('Errore di conversione')
    finally:
        client.disconnect()
