import asyncio
import logging

from athome import mqtt

LOGGER = logging.getLogger(__name__)

async def engage(loop):
    client = mqtt.local_client()
    await client.subscribe([
            ('$ATHOME/command', mqtt.QOS_1)
        ])
    while loop.is_running():
        LOGGER.debug('waiting for command')
        message = await client.deliver_message()
        LOGGER.info('COMMAND: ' + message.payload.decode('utf-8'))
        if message.payload.decode('utf-8') == 'shutdown':
            loop.stop()
    client.disconnect()
