# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

import asyncio
import logging
import importlib
from functools import partial

from transitions import Machine

LOGGER = logging.getLogger(__name__)

class SystemModule():
    """Base class for all athome system modules"""

    states = [
                'loaded',
                'ready',
                'running',
                'closed',
                'failure'
              ]

    transitions = [
            {
                'trigger':'initialize',
                'source':'loaded',
                'dest':'ready',
                'before': ['on_initialize']
                },
            {
                'trigger':'start',
                'source':'ready',
                'dest':'running',
                'before': ['_on_start']
                },
            {
                'trigger':'stop',
                'source':'running',
                'dest':'ready',
                'before': ['_on_stop']
                },
            {
                'trigger':'shutdown',
                'source':['loaded', 'ready', 'running'],
                'dest':'closed',
                'before': ['_on_shutdown']
                }
        ]

    def __init__(self, name):
        self.name = name
        self.machine = Machine(model=self,
                            states=SystemModule.states,
                            transitions=SystemModule.transitions,
                            initial='loaded')
        self.loop = None
        self.config = None
        self.run_task = None
        self.in_queue, self.out_queue = asyncio.Queue(), asyncio.Queue()

    def on_initialize(self, config):
        self.config = config

    async def run(self):
        LOGGER.debug("run does nothing by default")

    def on_start(self, loop):
        self.loop = loop

    def on_stop(self):
        raise NotImplementedError

    def on_shutdown(self):
        LOGGER.debug("on_shutdown does nothing by default")

    def _on_start(self, loop):
        if self.state is not 'ready':
            raise Exception('Subsystem not in "running" state')

        async def start_coro():
            self.on_start(loop)
            await self.run()

        self.run_task = asyncio.ensure_future(start_coro(), loop=self.loop)

    def _on_stop(self):
        self.on_stop()
        if not self.run_task.done():
            self.run_task.cancel()
        self.run_task = None

    def _on_shutdown(self):
        LOGGER.debug('Now awaiting shutdown_task for %s' % self.name)
        try:
            if self.state == 'running':
                self.on_stop()
            self.on_shutdown()
        except Exception as ex:
            LOGGER.exception("Subsystem %s shutdown in error" % self.name, ex)

        if self.run_task and not self.run_task.done():
            LOGGER.info("Now canceling run_task for subsystem")
            self.run_task.cancel()

        