# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

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
from athome.core import Message, MESSAGE_AWAIT

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

    def __init__(self, loop, name, module, mtime, await_queue):
        self.machine = Machine(model=self,
                            states=Plugin.states,
                            transitions=Plugin.transitions,
                            initial='ready')
        self.name = name
        self.module = module
        self.mtime = mtime
        self.loop = loop
        self.run_task = None
        self.await_queue = await_queue

    async def _wrap_coro(self):
        """Invoke plugin module 'engage' and wrap it into contextlib.suppress.CancelledError

        This metod is a *coroutine*

        """

        with contextlib.suppress(asyncio.CancelledError):
            await getattr(self.module, ENGAGE_METHOD)(self.loop)
                
    def _on_start(self, loop):
        """Create a new task for plugin"""

        self.run_task = asyncio.ensure_future(self._wrap_coro(), loop=self.loop)
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
        self.run_task.add_done_callback(callback)

    def _on_stop(self):
        """Before 'stop' event handler
        """

        if self.run_task and not self.run_task.done():
            LOGGER.debug('Plugin "engage" still running, cancel()')
            self.run_task.cancel()
        else:
            LOGGER.debug("")
        self.await_queue.put_nowait(Message(MESSAGE_AWAIT, self.run_task))
        self.run_task = None

    def _on_close(self):
        """Before 'close' event handler
        """

        if self.state == 'running':
            self._on_stop()
