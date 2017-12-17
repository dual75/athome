# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

import asyncio
import contextlib
import importlib
import logging

from athome import Message, MESSAGE_EVT, \
    MESSAGE_START, MESSAGE_STOP
from athome.system import SystemModule

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
            super().__init__('core')
            self._subsystems = {}
            self.loop = None
            self.event_task = None
            self.await_queue = asyncio.Queue()
            self.await_task = None
            self.__initialized = True

    def on_initialize(self):
        # Load _subsystems
        subsystems = self.config['subsystem']
        for name in [name for name in subsystems
                     if subsystems[name]['enable']
                     ]:
            LOGGER.debug('Loading module %s', name)
            module_name = 'athome.subsystems.{}'.format(name)
            try:
                module = importlib.import_module(module_name)
                subsystem_class = getattr(module, 'Subsystem')
                subsystem = subsystem_class(name)
                self._subsystems[name] = subsystem
                subsystem.initialize(
                    self.loop, 
                    self.config['subsystem'][name]['config']
                )
            except Exception as ex:
                LOGGER.exception('Error in initialization')
                raise ex

    def run_forever(self):
        """Execute run coroutine until stopped"""

        self.start()
        self.emit('athome_starting')
        self.await_task = asyncio.ensure_future(
            self._await_loop(),
            loop=self.loop
        )
        single_task = asyncio.gather(
            self.run_task, 
            self.await_task, 
            loop=self.loop
        )
        self.loop.run_until_complete(single_task)
        self.stopped()

    async def run(self):
        self.started()
        message = Message(MESSAGE_START, None)
        while message.type != MESSAGE_STOP:
            message = await self.message_queue.get()
            if message.type == MESSAGE_EVT:
                await self._propagate_message(message)
        await self._propagate_message(Message(MESSAGE_EVT, 'athome_stopped'))
        await asyncio.sleep(5, loop=self.loop)
        self.stopped()

        LOGGER.info('core.run() coro exiting')

    async def _await_loop(self):
        with contextlib.suppress(asyncio.CancelledError):
            while self.is_running() or not self.await_queue.empty():
                LOGGER.debug('awaiting for task')
                task = self.await_queue.get()
                try:
                    await task
                finally:
                    LOGGER.info('await ... done')
                self.await_queue.task_done()

    async def _propagate_message(self, evt):
        for subsystem in self._subsystems.values():
            await subsystem.message_queue.put(evt)

    def after_started(self):
        self.emit('athome_started')

    def _on_stop(self):
        self.emit('athome_stopping')
        self.message_queue.put_nowait(Message(MESSAGE_STOP, None))

    def after_stopped(self):
        all_tasks = asyncio.Task.all_tasks(loop=self.loop)
        list(map(lambda x: x.cancel(), all_tasks))
        if all_tasks:
            single = asyncio.gather(
                *all_tasks,
                loop=self.loop, 
                return_exceptions=True
            )
            self.loop.run_until_complete(single)

    def emit(self, evt):
        """Propagate event 'evt' to _subsystems"""

        self.message_queue.put_nowait(Message(MESSAGE_EVT, evt))

    def fire_and_forget(self, coro):
        """Create task from coro or awaitable and put it into await_queue"""

        task = asyncio.ensure_future(coro, loop=self.loop)
        self.await_queue.put_nowait(task)

    # shortcut for function
    faf = fire_and_forget

    @property
    def subsystems(self):
        return list(self._subsystems.keys())
