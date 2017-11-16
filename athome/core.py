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
            self.harvest_task = None
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

    async def _do_emit(self, evt):
        LOGGER.debug('Emit EVENT %s', evt)
        for subsystem in self.subsystems.values():
            await subsystem.on_event(evt)

    def emit(self, evt):
        self.await_queue.put_nowait(self._do_emit(evt))

    def _on_stop(self):
        self.emit('athome_stopped')
        self.await_queue.put_nowait('exit')
        self.run_task = None

    def on_shutdown(self):
        self.emit('athome_shutdown')
        self.await_queue.put_nowait('exit')

    async def run(self):
        message = 'start'
        while message != 'exit':
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
        LOGGER.info('Harvest coro exited')

    def run_until_complete(self, loop):
        self.start(loop)
        self.emit('athome_started')
        self.await_queue.put_nowait(self.run_task)

