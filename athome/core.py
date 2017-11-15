# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

import asyncio
import importlib
import logging
from functools import partial

from concurrent.futures import CancelledError 

from transitions import Machine

from athome.module import SystemModule

LOGGER = logging.getLogger(__name__)


class Core(SystemModule):
    """Core system module"""

    __instance = None

    def __new__(cls):
        if Core.__instance is None:
            Core.__instance = object.__new__(cls)
            Core.__instance.__initialized = False
        return Core.__instance

    def __init__(self):
        if not self.__initialized:
            super().__init__('core', asyncio.Queue())
            self.subsystems = {}
            self.loop = None
            self.__initialized = True

    def on_initialize(self, config):
        super().on_initialize(config)

        # Load subsystems
        for name in [name for name in config['subsystem'] 
                            if config['subsystem'][name]['enable']]:
            LOGGER.debug('Loading module {}'.format(name))
            module_name = 'athome.subsystem.{}'.format(name)
            module = importlib.import_module(module_name)
            subsystem_class = getattr(module, 'Subsystem')
            print(getattr(subsystem_class, '__init__'))
            LOGGER.debug('Subsystem class is %s' % str(subsystem_class))
            subsystem = self.subsystems[name] = subsystem_class(name, 
                                                    self.await_queue)
            LOGGER.info('Starting subsystem %s' % name)
            subsystem.initialize(config['subsystem'][name]['config'])

    def on_start(self, loop):
        self.loop = loop
        for subsystem in self.subsystems.values():
            subsystem.start(loop)

    async def run(self):
        await asyncio.gather(*[
            subsystem.run_task for subsystem in self.subsystems.values()
            ])
        
    def on_stop(self):
        for subsystem in self.subsystems.values():
            subsystem.stop()

    def on_shutdown(self):
        for subsystem in self.subsystems.values():
            subsystem.shutdown()

    async def burn(self):
        message = 'start'
        while message != 'stop':
            message = await self.await_queue.get()
            if isinstance(message, asyncio.Future):
                try:
                    await message
                except CancelledError as ex:
                    pass
                except Exception as ex:
                    LOGGER.warn("Exception %s on await" % str(ex))

    def _on_stop(self):
        self.await_queue.put_nowait(self.run_task)
        super()._on_stop()

    def run_until_complete(self, loop):
        burn_task = asyncio.ensure_future(self.burn(), loop=self.loop)
        self.start(loop)
        loop.run_until_complete(self.run_task)
        self.await_queue.put_nowait('stop')
        loop.run_until_complete(burn_task)

