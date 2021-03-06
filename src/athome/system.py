# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

import asyncio
import logging

from transitions import Machine

from athome.lib.jobs import Executor

from athome import Message,\
    MESSAGE_EVT,\
    MESSAGE_START,\
    MESSAGE_STOP,\
    MESSAGE_NONE,\
    MESSAGE_SHUTDOWN

LOGGER = logging.getLogger(__name__)


class SystemModule():
    """Base class for all athome system modules"""

    states = [
        'loaded',
        'initializing',
        'ready',
        'starting',
        'running',
        'stopping',
        'closed',
        'failed'
    ]

    transitions = [
        {
            'trigger': 'initialize',
            'source': 'loaded',
            'dest': 'initializing',
            'before': ['_on_initialize'],
            'after': ['_after_initialize']
        },
        {
            'trigger': 'initialized',
            'source': 'initializing',
            'dest': 'ready'
        },
        {
            'trigger': 'start',
            'source': 'ready',
            'dest': 'starting',
            'before': ['_on_start']
        },
        {
            'trigger': 'started',
            'source': 'starting',
            'dest': 'running',
            'after': ['_after_started'],
        },
        {
            'trigger': 'stop',
            'source': 'running',
            'dest': 'stopping',
            'before': ['_on_stop'],
        },
        {
            'trigger': 'stopped',
            'source': 'stopping',
            'dest': 'ready',
            'after': ['_after_stopped']
        },
        {
            'trigger': 'shutdown',
            'source': ['loaded', 'ready', 'running'],
            'dest':'closed',
            'before': ['_on_shutdown']
        },
        {
            'trigger': 'fail',
            'source': [
                'loaded',
                'initializing',
                'ready',
                'starting',
                'running',
                'stopping'
            ],
            'dest':'failed',
            'before': ['_on_fail']
        }
    ]

    def __init__(self, name):
        self.name = name
        self.machine = Machine(model=self,
                               states=SystemModule.states,
                               transitions=SystemModule.transitions,
                               initial='loaded')
        self.loop = None
        self.env = None
        self.config = None
        self.executor = Executor(self.loop)
        self.message_queue = asyncio.Queue()
        self.message_task = asyncio.ensure_future(self._wrap_message_cycle(), loop=self.loop)
        self._logger = None

    async def _wrap_message_cycle(self):
        await self.message_cycle()
        await self.executor.wait(0.5)

    def _on_initialize(self, loop, env, config):
        """Before 'initialize' callback"""

        LOGGER.debug("Initialize module %s", self.name)
        self.loop = loop
        self.env = env
        self.config = config
        self.on_initialize()

    def on_initialize(self):
        """on_initialize placeholder"""

        pass

    def _after_initialize(self, loop, env, config):
        self.initialized()

    def _on_start(self):
        """Before 'start' callback"""

        self.on_start()
        self.message_queue.put_nowait(Message(MESSAGE_START, None, None))

    def on_start(self):
        """Mandatory on_start method"""

        raise NotImplementedError
        
    async def message_cycle(self):
        """Mandatory message_queue consumer"""

        raise NotImplementedError

    def _after_started(self):
        """After 'start' callback"""

        self.after_started()

    def after_started(self):
        """after_start placeholder"""

        pass

    def _on_stop(self):
        """Before 'stop' callback"""
        
        self.on_stop()
        self.message_queue.put_nowait(Message(MESSAGE_STOP, None, None))

    def on_stop(self):
        """Perform module stop activities, mandatory"""

        raise NotImplementedError

    def _after_stopped(self):
        """After 'stop' callback"""

        self.after_stopped()

    def after_stopped(self):
        """Perform module stop activities, mandatory"""

        raise NotImplementedError

    def _on_shutdown(self):
        """Before 'shutdown' callback"""

        LOGGER.debug('shutting down %s', __name__)
        self.message_queue.put_nowait(Message(MESSAGE_SHUTDOWN, None, None))
        try:
            self.on_shutdown()
        except:
            LOGGER.exception("Subsystem %s shutdown in error", self.name)


    def on_shutdown(self):
        """on_shutdown placeholder"""

        pass

    def _on_fail(self):
        """Before 'fail' callback"""

        self.on_fail()
        LOGGER.error('SystemModule %s failed', self.name)

    def on_fail(self):
        """Before fail placeholder"""

        pass

    def _find_logger(self):
        pass

    def _log(self, level, msg, *args, **kwargs):
        assert level and isinstance(level, int)
        assert msg and isinstance(msg, str)
        logger = self._find_logger()
        if logger:
            logger.log('{}.{}'.format(__name__, self.__class__.__name__), level, msg, *args, **kwargs)
    
    def debug(self, msg, *args, **kwargs):
        self._log(logging.DEBUG, msg, *args, **kwargs)
    
    def info(self, msg, *args, **kwargs):
        self._log(logging.INFO, msg, *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        self._log(logging.WARNING, msg, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        self._log(logging.ERROR, msg, *args, **kwargs)


