# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

import logging

import json

from aiohttp import web
import aiohttp

from athome.submodule import SubsystemModule
from athome.api import mqtt
from athome.core import Core

LOGGER = logging.getLogger(__name__)

LOGGER.info('load aiohttp')


def http_failure(msg):
    response_data = {'status': 'failure', "message": msg}
    body = json.dumps(response_data).encode('utf-8')
    return aiohttp.web.Response(body=body, content_type="application/json")


async def decode(request):
    try:
        result = await request.json()
        return result
    except json.decoder.JSONDecodeError:
        return http_failure("data not properly formated")


async def manage_handler(request):
    json_request = await decode(request)
    if json_request['command'] == 'stop':
        Core().stop()

    response_data = {'status': 'ok'}
    body = json.dumps(response_data).encode('utf-8')
    return aiohttp.web.Response(body=body, content_type="application/json")


async def publish_handler(request):
    json_request = await decode(request)
    client = await mqtt.local_client()
    await client.publish(
        json_request['topic'],
        json_request['message'].encode('utf-8'),
        'qos' in json_request and json_request['qos'] or 0
    )
    client.disconnect()
    response_data = {'status': 'ok'}
    body = json.dumps(response_data).encode('utf-8')
    return aiohttp.web.Response(body=body, content_type="application/json")


class Subsystem(SubsystemModule):
    """Subsystem embedding aiohttp"""

    def __init__(self, name, await_queue):
        super().__init__(name, await_queue)
        self.app = None

    def on_start(self, loop):
        """Instantiate a fresh server"""

        self.core.emit('aiohttp_starting')
        self.app = aiohttp.web.Application(loop=self.core.loop)
        self.app.router.add_route('POST', '/manage', manage_handler)
        self.app.router.add_route('POST', '/publish', publish_handler)

    async def run(self):
        """Start broker"""

        LOGGER.debug('starting aiohttp server')
        await self.core.loop.create_server(self.app.make_handler(),
                                           self.config['addr'],
                                           self.config['port']
                                           )
        self.core.emit('aiohttp_started')

    def on_stop(self):
        """Shut down aiohttp application"""

        async def stop_server():
            self.core.emit('aiohttp_stopping')
            await self.server.shutdown()
            self.core.emit('aiohttp_stopped')
        self.core.faf(stop_server())
