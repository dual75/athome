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


async def core_handler(request):
    json_request = await decode(request)
    core = Core()
    command = json_request['command']
    if command == 'stop':
        core.stop()
    elif command == 'restart':
        core.restart()

    response_data = {'status': 'ok'}
    body = json.dumps(response_data).encode('utf-8')
    return aiohttp.web.Response(body=body, content_type="application/json")


async def subsystem_handler(request):
    json_request = await decode(request)
    core = Core()
    name = json_request['name']
    command = json_request['command']
    if command == 'start':
        core.subsystems[name].start(core.loop)
    elif command == 'stop':
        core.subsystems[name].stop()
    elif command == 'restart':
        core.subsystems[name].restart()

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
    """Subsystem embedding http"""

    def __init__(self, name, await_queue):
        super().__init__(name, await_queue)
        self.app = None

    def on_start(self):
        """Instantiate a fresh server"""

        self.core.emit('http_starting')
        self.app = aiohttp.web.Application(loop=self.core.loop)
        self.app.router.add_route('POST', '/core', core_handler)
        self.app.router.add_route('POST', '/publish', publish_handler)
        self.app.router.add_route('POST', '/subsystem', subsystem_handler)

    async def run(self):
        """Start broker"""

        LOGGER.debug('starting http server')
        await self.core.loop.create_server(self.app.make_handler(),
                                           self.config['addr'],
                                           self.config['port']
                                           )
        self.core.emit('http_started')

    def on_stop(self):
        """Shut down aiohttp application"""

        async def stop_server():
            self.core.emit('http_stopping')
            await self.app.shutdown()
            self.core.emit('http_stopped')
        self.core.faf(stop_server())

