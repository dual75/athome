# Copyright (c) 2017 Alessandro Duca
#
# See the file license.txt for copying permission.

import os, sys
import asyncio

from hbmqtt.broker import Broker

from hbmqtt.client import MQTTClient, ClientException
from hbmqtt.mqtt.constants import QOS_0, QOS_1, QOS_2

broker = None
config = None

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


async def run_broker(config_parm):
    """Start hbmqtt broker

    Parameters
    ----------
    config_parm: dict
        Python dictionary holding broker configuration
    """
    
    global broker, config
    config = config_parm
    broker = Broker(config)
    await broker.start()


async def stop_broker():
    """Stop hbmqtt"""
    
    global broker
    if broker:
        await broker.shutdown()
    broker = None
    
