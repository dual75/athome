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
            self.__initialized = True

    def on_initialize(self):
        # Load subsystems
        for name in [name for name in self.config['subsystem']
                     if self.config['subsystem'][name]['enable']
                    ]:
            LOGGER.debug('Loading module %s', name)
            module_name = 'athome.subsystem.{}'.format(name)
            module = importlib.import_module(module_name)
            subsystem_class = getattr(module, 'Subsystem')
            subsystem = subsystem_class(name, self.await_queue)
            self.subsystems[name] = subsystem
            subsystem.initialize(self.config['subsystem'][name]['config'])

    def after_start(self, loop):
        self.emit("athome_started")

    async def _do_emit(self, evt):
        LOGGER.debug('Emit event: %s', evt)
        for subsystem in self.subsystems.values():
            await subsystem.on_event(evt)

    def emit(self, evt):
        """Propagate event 'evt' to subsystems"""

        self.faf(self._do_emit(evt))

    def fire_and_forget(self, coro):
        """Create task from coro or awaitable and put it into await_queue"""

        task = asyncio.ensure_future(coro, loop=self.loop)
        self.await_queue.put_nowait(task)

    # shortcut for function
    faf = fire_and_forget

    def on_stop(self):
        self.emit('athome_stopping')

    def after_stop(self):
        self.emit('athome_stopped')

    def on_shutdown(self):
        self.emit('athome_shutdown')
        self.await_queue.put_nowait('exit')

    def on_fail(self):
        """Failure event handler

        Forcibly cancels all running tasks for subsystems and invoke
        fail() method bypassing the event mechanism.

        """
        for subsystem in self.subsystems.values():
            run_task = subsystem.run_task
            if run_task:
                if not run_task.done():
                    run_task.cancel()
                self.await_queue.put_nowait(run_task)
            subsystem.fail()
        self.await_queue.put('exit')

    async def run(self):
        message = 'start'
        while message != 'exit':
            message = await self.await_queue.get()
            if isinstance(message, asyncio.Future):
                try:
                    if LOGGER.isEnabledFor(logging.DEBUG):
                        LOGGER.info('Now awaiting %s...', str(message))
                    await message
                except CancelledError as ex:
                    LOGGER.info('await ... caught CancelledError ...')
                except Exception as ex:
                    LOGGER.warning("await... caught %s on await ...", ex)
                finally:
                    LOGGER.info('await ... done')
        LOGGER.info('Harvest coro exited')

    def run_forever(self, loop):
        """Execute run coroutine until stopped"""

        self.start(loop)
        loop.run_until_complete(self.run_task)

