# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

from hbmqtt.broker import Broker

from hbmqtt.client import MQTTClient
from hbmqtt.mqtt.constants import QOS_1

import athome

LOCAL_CLIENT_CONFIG = {
    'keep_alive': 30,
    'default_qos': QOS_1
}


async def local_client():
    """Create a mqtt client connected to the local broker

    This method is a *coroutine*

    """

    config = athome.core.Core().config
    url = config['subsystem']['hbmqtt']['config']['listeners']['local']['bind']
    result = MQTTClient(config=LOCAL_CLIENT_CONFIG)
    await result.connect('mqtt://%s' % url, cleansession=True)
    return result
