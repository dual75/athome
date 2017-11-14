# Copyright (c) 2017 Alessandro Duca
#
# See the file license.txt for copying permission.

"""
"""

import os
import unittest

import asyncio
import subprocess

from . import common
from athome import mqtt

BROKER_CONFIG = {
    'listeners': {
        'default': {
            'max-connections': 5000,
            'type': 'tcp'
            }, 
        'local': {
            'bind': 'localhost:1883'
            }
        },
    'timeout-disconnect-delay': 2,
    'auth': {
        'plugins': ['auth.anonymous'],
        'allow-anonymous': True
        }
    }


class HBMqttSubsystemTest(common.SubsystemTest):
    """Test hbmqtt subsystem client"""

    def setUp(self):
        super().setUp()
        mqtt.config = BROKER_CONFIG
        self.loop.run_until_complete(mqtt.run_broker(BROKER_CONFIG))

    def tearDown(self):
        self.loop.run_until_complete(mqtt.stop_broker())
        super().tearDown()

    def test_publish_subscribe(self):
        """mqtt.local_client() returns a connected client"""
        
        async def test():
            client = await mqtt.local_client()
            await client.subscribe([
                ('topic/test', mqtt.QOS_1),
            ])
            await client.publish('topic/test', b'message', mqtt.QOS_1)
            message = await client.deliver_message()
            client.disconnect()
            return message
        message = self.loop.run_until_complete(test())
        self.assertNotEqual(len(message.publish_packet.payload.data), 0)
        
if __name__ == '__main__':
    unittest.main()
