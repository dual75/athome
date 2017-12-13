# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.


import logging

import json

import aiohttp
from aiohttp import web

from athome.submodule import SubsystemModule
from athome.core import Core
from athome.lib.management import managed, ManagedObject
from athome.lib.locator import Cache, NameError

LOGGER = logging.getLogger(__name__)

CT_JSON = 'application/json'

async def decode(request):
    try:
        result = await request.json()
        return result
    except json.decoder.JSONDecodeError:
        return http_failure("data not properly formated")


def prepare_outcome():
    result = dict()
    result['outcome'] = 0
    result['status'] = 'ok'
    result['data'] = None
    return result


def error_outcome(response, msg, code=-1):
    response['outcome'] = code
    response['status'] = msg


def find_managed_subsystem(request):
    cache = Cache()
    name = request.match_info['name']
    subsystem_path = 'subsystem/{}'.format(name)
    managed_path = 'managed/{}'.format(subsystem_path)
    try:
        managed = cache.lookup(managed_path)
    except NameError as ex:
        subsystem = cache.lookup(subsystem_path)
        managed = ManagedObject(subsystem)
        cache.register(managed_path, managed)
    return managed


async def get_subsystem_handler(request):
    managed = find_managed_subsystem(request)
    return aiohttp.web.Response(body=managed.json(), content_type=CT_JSON)


async def post_subsystem_handler(request):
    managed = find_managed_subsystem(request)
    method = request.match_info['method']
    args = await decode(request)
    result = prepare_outcome()
    try:
        call_result = managed.invoke(method, args)
        result['data'] = call_result
    except Exception as ex:
        error_outcome(result, repr(ex))
    result = json.dumps(result)
    return aiohttp.web.Response(body=result, content_type=CT_JSON)


def find_managed_core():
    core_path = 'core'
    managed_path = 'managed/{}'.format(core_path)
    cache = Cache()
    try:
        managed = cache.lookup(managed_path)
    except NameError as ex:
        core = Core()
        managed = ManagedObject(core)
        cache.register(managed_path, managed)
    return managed


async def get_core_handler(request):
    managed = find_managed_core()
    return aiohttp.web.Response(body=managed.json(), content_type=CT_JSON)


async def post_core_handler(request):
    managed = find_managed_core()
    result = prepare_outcome()
    try:
        args = await decode(request)
        method = request.match_info['method']
        call_result = managed.invoke(method, args)
        result['data'] = call_result
    except Exception as ex:
        error_outcome(result, repr(ex))
    result = json.dumps(result)
    return aiohttp.web.Response(body=result, content_type=CT_JSON)


class Subsystem(SubsystemModule):
    """Subsystem embedding http"""

    def __init__(self, name):
        super().__init__(name)
        self.app = None

    def on_start(self):
        """Instantiate a fresh server"""

        self.core.emit('http_starting')
        self.app = aiohttp.web.Application(loop=self.core.loop)
        self.app.router.add_route('GET', '/core', get_core_handler)
        self.app.router.add_route('POST', '/core/{method}', post_core_handler)
        self.app.router.add_route('GET', '/subsystem/{name}', get_subsystem_handler)
        self.app.router.add_route('POST', '/subsystem/{name}/{method}', post_subsystem_handler)

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

    @managed
    def greet(self, value):
        return 'ciao {}'.format(value)

    @property
    def status(self):
        return self.state
