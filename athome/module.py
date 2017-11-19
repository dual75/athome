# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

import asyncio
import logging

from transitions import Machine

LOGGER = logging.getLogger(__name__)


class SystemModule():
    """Base class for all athome system modules"""

    states = [
                'loaded',
                'ready',
                'running',
                'closed',
                'failed'
              ]

    transitions = [
            {
                'trigger':'initialize',
                'source':'loaded',
                'dest':'ready',
                'before': ['_on_initialize'],
                'after': ['_after_initialize']
                },
            {
                'trigger':'start',
                'source':'ready',
                'dest':'running',
                'before': ['_on_start'],
                'after': ['_after_start']
                },
            {
                'trigger':'stop',
                'source':'running',
                'dest':'ready',
                'before': ['_on_stop'],
                'after': ['_after_stop']
                },
            {
                'trigger':'shutdown',
                'source':['loaded', 'ready', 'running'],
                'dest':'closed',
                'before': ['_on_shutdown'],
                'after': ['_after_shutdown']
                },
            {
                'trigger':'fail',
                'source':['loaded', 'ready', 'running'],
                'dest':'failed',
                'before': ['_on_fail']
                }
        ]

    def __init__(self, name, await_queue=None):

        self.name = name
        self.machine = Machine(model=self,
                            states=SystemModule.states,
                            transitions=SystemModule.transitions,
                            initial='loaded')
        self.loop = None
        self.config = None
        self.run_task = None
        self.await_queue = await_queue

    def on_initialize(self):
        """on_initialize placeholder"""

        pass

    def _on_initialize(self, config):
        """On 'initialize' event handler"""

        LOGGER.debug("Initialize module %s", self.name)
        self.config = config
        self.on_initialize()

    def after_initialize(self, config):
        """after_initialize placeholder"""

        pass

    def _after_initialize(self, config):
        """After 'initialize' event handler"""

        self.after_initialize(config)

    async def run(self):
        """Placeholder for run coroutine"""

        LOGGER.debug("run does nothing by default")

    def on_start(self, loop):
        """on_start placeholder"""

        pass

    def _on_start(self, loop):
        """'start' event handler"""

        self.loop = loop
        self.on_start(loop)
        self.run_task = asyncio.ensure_future(self.run(), loop=loop)

    def after_start(self, loop):
        """after_start placeholder"""

        pass

    def _after_start(self, loop):
        self.after_start(loop)

    def on_stop(self):
        """Perform module stop activities, mandatory"""

        raise NotImplementedError
    
    def _on_stop(self):
        """On 'stop' event handler"""

        self.on_stop()
        if not self.run_task.done():
            self.run_task.cancel()
        self.await_queue.put_nowait(self.run_task)
        self.run_task = None

    def after_stop(self):
        """after_start placeholder"""

        pass

    def _after_stop(self):
        """After 'stop' callback"""

        self.after_stop()

    def on_shutdown(self):
        """on_shutdown placeholder"""

        pass

    def _on_shutdown(self):
        """On 'shutdown' event handler"""        

        try:
            if self.is_running():
                self._on_stop()
            self.on_shutdown()
        except Exception as ex:
            LOGGER.exception("Subsystem %s shutdown in error: %s", 
                             self.name, ex)

    def after_shutdown(self):
        """after_shutdown placeholder"""

        pass

    def _after_shutdown(self):
        """After 'shutdown' event handler"""

        self.after_shutdown()

    def on_fail(self):
        """On fail placeholder"""

        pass

    def _on_fail(self):
        """On 'fail' event handler"""

        self.on_fail()
        LOGGER.error('SystemModule %s failed', self.name)


