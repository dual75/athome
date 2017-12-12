    # Copyright (c) 2017 Alessandro Duca
    #
    # See the file LICENCE for copying permission.

import asyncio
import logging
import multiprocessing

from transitions import Machine
from athome import Message, MESSAGE_AWAIT

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
                'trigger':'initialize',
                'source':'loaded',
                'dest':'initializing',
                'before': ['_on_initialize'],
                'after': ['_after_initialize']
                },
            {
                'trigger':'initialized',
                'source':'initializing',
                'dest':'ready'
                },
            {
                'trigger':'start',
                'source':'ready',
                'dest':'starting',
                'before': ['_on_start']
                },
            {
                'trigger':'started',
                'source':'starting',
                'dest':'running',
                'after': ['_after_started'],
                },
            {
                'trigger':'stop',
                'source':'running',
                'dest':'stopping',
                'before': ['_on_stop'],
                },
            {
                'trigger':'stopped',
                'source':'stopping',
                'dest':'ready',
                'after': ['_after_stopped']
                },
            {
                'trigger':'shutdown',
                'source':['loaded', 'ready', 'running'],
                'dest':'closed',
                'before': ['_on_shutdown']
                },
            {
                'trigger':'fail',
                'source':[
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

    def __init__(self, name, event_queue=None):
        self.name = name
        self.machine = Machine(model=self,
                            states=SystemModule.states,
                            transitions=SystemModule.transitions,
                            initial='loaded')
        self.loop = None
        self.config = None
        self.run_task = None
        self.event_queue = event_queue

    def _on_initialize(self, loop, config):
        """Before 'initialize' callback"""

        LOGGER.debug("Initialize module %s", self.name)
        self.loop = loop
        self.config = config
        self.on_initialize()

    def on_initialize(self):
        """on_initialize placeholder"""

        pass

    def _after_initialize(self, loop, config):
        self.initialized()

    async def run(self):
        """Placeholder for run coroutine"""

        LOGGER.debug("run does nothing by default")

    def _on_start(self):
        """Before 'start' callback"""

        self.on_start()
        self.run_task = asyncio.ensure_future(self.run(), loop=self.loop)

    def on_start(self):
        """on_start placeholder"""

        pass

    def _after_started(self):
        """After 'start' callback"""

        self.after_started()

    def after_started(self):
        """after_start placeholder"""

        pass

    def _on_stop(self):
        """Before 'stop' callback"""

        self.on_stop()
        #if not self.run_task.done():
        #    self.run_task.cancel()
        #self.await_queue.put_nowait(Message(MESSAGE_AWAIT, self.run_task))
        #self.run_task = None

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
        try:
            self.on_shutdown()
        except Exception as ex:
            LOGGER.exception("Subsystem %s shutdown in error: %s", 
                             self.name, ex)

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

    @property
    def status(self):
        return self.state


