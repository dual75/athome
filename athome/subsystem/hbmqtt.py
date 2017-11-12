# Copyright (c) 2017 Alessandro Duca
#
# See the file license.txt for copying permission.

import os, sys
import asyncio

from hbmqtt.broker import Broker

from hbmqtt.client import MQTTClient, ClientException
from hbmqtt.mqtt.constants import QOS_0, QOS_1, QOS_2

_broker = None
_loop = None

LOCAL_CLIENT_CONFIG = {
        'keep_alive': 30,
        'default_qos': QOS_0
    }

async def local_client():
    """Create a mqtt client connected to the local broker"""
    
    result = MQTTClient(config=LOCAL_CLIENT_CONFIG)
    await result.connect(
        'mqtt://{}/'.format(config['listeners']['local']['bind']),
        cleansession=True
        )
    return result


async def startup(loop, config, in_queue):
    """Start hbmqtt broker

    Parameters
    ----------
    config_parm: dict
        Python dictionary holding broker configuration
    """
    
    global _broker, _loop
    _loop = loop
    _broker = Broker(config)
    await _broker.start()
    in_queue.get()


async def shutdown():
    """Stop hbmqtt"""
    global _broker 
    if _broker:
        await _broker.shutdown()
    _broker = None
    
