# Copyright (c) 2017 Alessandro Duca
#
# See the file license.txt for copying permission.

import os, sys
import asyncio
import logging
import functools
import concurrent
import importlib
import contextlib
from functools import partial

from transitions import Machine

import athome

ENGAGE_METHOD   = 'engage'
SHUTDOWN_METHOD = 'shutdown'

LOGGER = logging.getLogger(__name__)

class Plugin(object):
    """Plugin module wrapper and execution logic

    """

    states = [
        'ready',
        'running',
        'closed'
    ]

    transitions = [
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
                'trigger':'close',
                'source': ['loaded', 'ready', 'running'],
                'dest':'ready',
                'before': ['_on_close']
                }
    ]

    def __init__(self, loop, name, module, mtime):
        self.machine = Machine(model=self,
                            states=Plugin.states,
                            transitions=Plugin.transitions,
                            initial='ready')
        self.name = name
        self.module = module
        self.mtime = mtime
        self.loop = loop
        self._task_coro = None

    async def _wrap_coro(self):
        """Invoke plugin module 'engage' and wrap it into contextlib.suppress.CancelledError

        This metod is a *coroutine*

        """

        with contextlib.suppress(concurrent.futures.CancelledError):
            try:
                await getattr(self.module, ENGAGE_METHOD)(self.loop)
            except Exception as ex:
                LOGGER.exception('Exception occurred in plugin {}'.format(self.name), ex)
                
    def _on_start(self, loop):
        """Create a new task for plugin"""

        self._task_coro = asyncio.ensure_future(self._wrap_coro(), loop=self.loop)
        shutdown = getattr(self.module, SHUTDOWN_METHOD, None)
        callback = None
        if shutdown:
            def callback_func(future):
                shutdown()
            callback = callback_func
        else:
            def callback_func(future):
                LOGGER.debug("Dummy callback() for plugin %s run_task" % self.name)
            callback = callback_func
        self._task_coro.add_done_callback(callback)

    def _on_stop(self):
        """Before 'stop' event handler
        """

        if not self._task_coro.done():
            self._task_coro.cancel()
        self._task_coro = None

    def _on_close(self):
        """Before 'close' event handler
        """

        if self.state == 'running':
            self._on_stop()
