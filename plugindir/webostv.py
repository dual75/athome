import asyncio
import logging

from athome.api import mqtt
from pylgtv import WebOsClient

WEBOSTV_IP = '192.168.1.131'
TV_TOPIC = 'tv/0'

LOGGER = logging.getLogger(__name__)

g_mute = None
g_volume = None
g_app = None

tv = WebOsClient(WEBOSTV_IP)

async def task_poll(loop):
    while True:
        try:
            channel = await tv.get_current_channel()
            await perform_poll(loop)
        except OSError:
            LOGGER.exception('Error connecting to tv')
            await asyncio.sleep(300)

async def perform_poll(loop):
    global g_mute, g_volume, g_app
    try:
        async with mqtt.local_client(True) as mqtt_client: 
            while True:
                

                muted = await tv.get_muted()
                volume = await tv.get_volume()
                app = await tv.get_current_app()

                if mqtt_client.session:
                    # handle mute
                    if not g_mute or g_mute != muted:
                        LOGGER.debug('Update mute to extern')
                        g_mute = muted
                        await mqtt_client.publish(
                            'extern/%s/mute' % TV_TOPIC, 
                            '%d' % (muted and 1 or 0)
                        )
                    await mqtt_client.publish(
                        '%s/mute' % TV_TOPIC,
                        '%d' % (muted and 1 or 0)
                    )

                    # handle volume
                    if not g_volume or g_volume != volume:
                        LOGGER.debug('Update volume to extern')
                        g_mute = volume
                        await mqtt_client.publish(
                            'extern/%s/volume' % TV_TOPIC, 
                            '%d' % (volume)
                        )
                    await mqtt_client.publish(
                        '%s/volume' % TV_TOPIC, 
                        '%d' % (volume)
                    )

                    # handle current app
                    if not g_app or g_app != app:
                        LOGGER.debug('Update app to extern')
                        g_app = app
                        await mqtt_client.publish(
                            'extern/%s/app' % TV_TOPIC, 
                            '%d' % (volume)
                        )
                    await mqtt_client.publish(
                        '%s/app' % TV_TOPIC, 
                        '%d' % (app)
                    )

                await asyncio.sleep(5)
    except asyncio.CancelledError:
        pass
    except:
        LOGGER.exception('Error in task_poll') 


async def task_set(loop):
    global g_mute, g_volume
    try:
        tv = WebOsClient(WEBOSTV_IP)
        async with mqtt.local_client(True) as mqtt_client: 
            await mqtt_client.subscribe(
                ('%s/mute/set' % TV_TOPIC, mqtt.QOS_1),
                ('%s/volume/set' % TV_TOPIC, mqtt.QOS_1)
                )

            while True:
                message = await mqtt_client.deliver_message()
                data = message.data.decode('utf-8')
                LOGGER.debug('delivered on topic %d, message: %s', message.topic, data)
                if message.topic == '%s/mute/set' % TV_TOPIC:
                    await tv.set_mute(data == '1' and True or False)
                elif message.topic == '%s/volume/set' % TV_TOPIC:
                    await tv.set_volume(int(data))
            
    except asyncio.CancelledError:
        pass
    except:
        LOGGER.exception('Error in task_set') 
    
def main():
    loop = asyncio.get_event_loop()
    tasks = asyncio.gather(
        task_poll(loop),
        task_set(loop)
    )
    task = asyncio.ensure_future(tasks)
    loop.run_until_complete(task)
    loop.close()

if __name__ == '__main__':
    main()
