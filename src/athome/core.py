# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

import asyncio
import importlib
import logging

from athome import Message,\
    MESSAGE_EVT,\
    MESSAGE_START,\
    MESSAGE_STOP,\
    MESSAGE_NONE,\
    MESSAGE_SHUTDOWN
from athome.system import SystemModule
from athome.lib.locator import Cache
from athome.lib.management import managed

SHUTDOWN_TIMEOUT = 2

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
            self._cache = Cache()
            self.__initialized = True

    def on_initialize(self):
        # Load _subsystems
        
        subsystems = self.config['subsystem']
        for name in [name for name in subsystems
                     if subsystems[name]['enable']
                     ]:
            module_class = subsystems[name]['class']
            try:
                subsystem_class = self._load_class(module_class)
                subsystem = subsystem_class(name)
                self._subsystems[name] = subsystem
                subsystem.initialize(
                    self.loop, 
                    self.env,
                    self.config['subsystem'][name]['config']
                )
                self._cache.register('subsystem/{}'.format(name), subsystem)
            except Exception as ex:
                LOGGER.exception('Error in initialization')
                raise ex

    @staticmethod
    def _load_class(class_name):
        assert '.' in class_name
        module_name, class_name = class_name.rsplit('.', 1)
        module = importlib.import_module(module_name)
        class_ = getattr(module, class_name)
        from athome.subsystem import SubsystemModule
        assert issubclass(class_, SubsystemModule)
        return class_

    async def run_forever(self):
        """Execute run coroutine until stopped"""
        
        self.start()
        await self.message_job

    async def message_cycle(self):
        message = Message(MESSAGE_NONE, None)
        while message.type != MESSAGE_SHUTDOWN:
            message = await self.message_queue.get()
            if message.type == MESSAGE_START:
                self.started()
            elif message.type == MESSAGE_STOP:
                self.stopped()
            elif message.type == MESSAGE_EVT:
                await self._propagate_message(message)
            elif message.type == MESSAGE_SHUTDOWN:
                pass
        await asyncio.sleep(SHUTDOWN_TIMEOUT, loop=self.loop)

    async def _propagate_message(self, evt):
        for subsystem in self._subsystems.values():
            await subsystem.message_queue.put(evt)

    def on_start(self):
        self.emit('athome_starting')

    def after_started(self):
        self.emit('athome_started')

    def on_stop(self):
        self.emit('athome_stopping')

    def after_stopped(self):
        self.emit('athome_stopped')

    def on_shutdown(self):
        self.emit('athome_shutdown')

    def emit(self, evt):
        """Propagate event 'evt' to _subsystems"""

        self.message_queue.put_nowait(Message(MESSAGE_EVT, evt))

    @property
    def subsystems(self):
        return list(self._subsystems.keys())

    @property
    def status(self):
        return self.state

    @managed('stop')
    def managed_stop(self):
        self.stop()

    @managed('shutdown')
    def managed_shutdown(self):
        self.shutdown()
