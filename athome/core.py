# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

import asyncio
import importlib
import logging

from concurrent.futures import CancelledError 

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
            self.burn_task = None
            self.__initialized = True

    def on_initialize(self, config):
        super().on_initialize(config)

        # Load subsystems
        for name in [name for name in config['subsystem']
                     if config['subsystem'][name]['enable']
                    ]:
            LOGGER.debug('Loading module %s', name)
            module_name = 'athome.subsystem.{}'.format(name)
            module = importlib.import_module(module_name)
            subsystem_class = getattr(module, 'Subsystem')
            print(getattr(subsystem_class, '__init__'))
            LOGGER.debug('Subsystem class is %s', subsystem_class)
            subsystem = subsystem_class(name, self.await_queue)
            self.subsystems[name] = subsystem
            LOGGER.info('Starting subsystem %s', name)
            subsystem.initialize(config['subsystem'][name]['config'])

    def emit(self, evt):
        async def do_emit(evt):
            for subsystem in self.subsystems.values():
                await subsystem.on_event(evt)
        self.await_queue.put_nowait(do_emit(evt))

    def on_start(self, loop):
        self.loop = loop
        self.burn_task = asyncio.ensure_future(self.burn(), loop=self.loop)
        self.emit('athome_start')

    async def run(self):
        await asyncio.gather(*[
            subsystem.run_task for subsystem in self.subsystems.values()
            ])
       
    def on_stop(self):
        self.emit('athome_stop')

    def on_shutdown(self):
        self.emit('athome_shutdown')

    async def burn(self):
        message = 'start'
        while message != 'stop':
            message = await self.await_queue.get()
            LOGGER.debug('Got message %s from self.await_queue', str(message))
            if isinstance(message, asyncio.Future):
                try:
                    LOGGER.info('Now awaiting %s...', str(message))
                    await message
                except CancelledError as ex:
                    LOGGER.info('... caught CancelledError ...')
                except Exception as ex:
                    LOGGER.warning("... caught %s on await ...", ex)
                finally:
                    LOGGER.info('... done')
        LOGGER.info('Burn coro exited')

    def _on_stop(self):
        self.await_queue.put_nowait(self.run_task)
        super()._on_stop()

    def run_until_complete(self, loop):
        self.start(loop)
        loop.run_until_complete(self.run_task)
        self.await_queue.put_nowait('stop')
        loop.run_until_complete(self.burn_task)

