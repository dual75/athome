# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

import asyncio
import importlib
import logging

from athome import Message, MESSAGE_EVT, \
    MESSAGE_START, MESSAGE_STOP
from athome.system import SystemModule

STOP_TIMEOUT = 5

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
        self.loop.run_until_complete(self.run_task)
        self.stopped()

    async def run(self):
        self.started()
        message = Message(MESSAGE_START, None)
        while message.type != MESSAGE_STOP:
            message = await self.message_queue.get()
            if message.type == MESSAGE_EVT:
                await self._propagate_message(message)
        await self._propagate_message(Message(MESSAGE_EVT, 'athome_stopped'))
        await asyncio.sleep(STOP_TIMEOUT, loop=self.loop)
        self.stopped()

        LOGGER.info('core.run() coro exiting')

    async def _propagate_message(self, evt):
        for subsystem in self._subsystems.values():
            await subsystem.message_queue.put(evt)

    def after_started(self):
        self.emit('athome_started')

    def _on_stop(self):
        self.emit('athome_stopping')
        self.message_queue.put_nowait(Message(MESSAGE_STOP, None))

    def emit(self, evt):
        """Propagate event 'evt' to _subsystems"""

        self.message_queue.put_nowait(Message(MESSAGE_EVT, evt))

    @property
    def subsystems(self):
        return list(self._subsystems.keys())
