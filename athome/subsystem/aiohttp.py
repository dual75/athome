# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

import logging

from aiohttp import web
from athome.submodule import SubsystemModule

LOGGER = logging.getLogger(__name__)

LOGGER.info('load aiohttp')

async def handler(request):
    return web.Response(text="OK")


class Subsystem(SubsystemModule):
    """Subsystem embedding aiohttp"""

    def __init__(self, name, await_queue):
        super().__init__(name, await_queue)
        self.server = None

    def on_start(self, loop):
        """Instantiate a fresh server"""

        self.server = web.Server(handler)
        self.core.emit('aiohttp_starting')

    async def run(self):
        """Start broker"""
        
        LOGGER.debug('starting aiohttp server')     
        await self.loop.create_server(server,
                                      self.conf['addr'], 
                                      self.conf['port'])

    def on_stop(self):
        self.server = None

