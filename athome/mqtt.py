# Copyright (c) 2017 Alessandro Duca
#
# See the file license.txt for copying permission.

import os, sys
import asyncio

from hbmqtt.broker import Broker

from hbmqtt.client import MQTTClient, ClientException
from hbmqtt.mqtt.constants import QOS_0, QOS_1, QOS_2

from athome.core import config

broker = None
config = None

LOCAL_CLIENT_CONFIG = {
        'keep_alive': 30,
        'default_qos': QOS_0
    }

async def local_client():
    """Create a mqtt client connected to the local broker"""

    config_ = config['subsystem']['hbmqtt']
    
    result = MQTTClient(config=LOCAL_CLIENT_CONFIG)
    await result.connect(
        'mqtt://{}/'.format(config_['listeners']['local']['bind']),
        cleansession=True
        )
    return result

