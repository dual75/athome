# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

import asyncio
import logging
from contextlib import suppress

from transitions import Machine

from athome.core import Message

ENGAGE_METHOD = 'engage'
DONE_CALLBACK = 'done_callback'

LOGGER = logging.getLogger(__name__)


class Task():
    """Task module wrapper and execution logic

    """

    states = [
        'ready',
        'running',
        'closed'
    ]

    transitions = [
        {
            'trigger': 'start',
            'source': 'ready',
            'dest': 'running',
            'before': ['_on_start']
        },
        {
            'trigger': 'stop',
            'source': 'running',
            'dest': 'ready',
            'before': ['_on_stop']
        },
        {
            'trigger': 'close',
            'source': ['loaded', 'ready', 'running'],
            'dest':'ready',
            'before': ['_on_close']
        }
    ]

    def __init__(self, loop, name, module, mtime, task_coros, await_queue):
        self.machine = Machine(model=self,
                               states=Task.states,
                               transitions=Task.transitions,
                               initial='ready')
        self.name = name
        self.module = module
        self.mtime = mtime
        self.loop = loop
        self.run_task = None
        self.tasks_coros = task_coros
        self.await_queue = await_queue

    def task_done_callback(self, future):
        if not future.cancelled() and future.exception():
            LOGGER.error('Exception %s, occurred in %s',
                future.exception(),
                self.name, 
                exc_info=True)

    async def _wrap_coro(self):
        """Invoke plugin module 'engage' and wrap it into contextlib.suppress.CancelledError

        This metod is a *coroutine*

        """

        loop = asyncio.get_event_loop()
        all_tasks = asyncio.gather(
                *[task(loop) for task in self.tasks_coros.values()]
        )
        all_tasks.add_done_callback(self.task_done_callback)
        await all_tasks

    def _on_start(self, loop):
        """Create a new task for plugin"""

        self.run_task = asyncio.ensure_future(
            self._wrap_coro(), loop=self.loop)
        shutdown = getattr(self.module, DONE_CALLBACK, None)
        callback = None
        if shutdown:
            def callback_func(future):
                """Upon 'engage' coro  completion call cleanup code"""
                shutdown()
            callback = callback_func
        else:
            def callback_func(future):
                """Dummy completion call cleanup code"""
                pass
            callback = callback_func
        self.run_task.add_done_callback(callback)

    def _on_stop(self):
        """Before 'stop' event handler
        """

        if self.run_task:
            if not self.run_task.done():
                LOGGER.debug('Plugin "engage" still running, cancel()')
                self.run_task.cancel()
            self.await_queue.put_nowait(self.run_task)
            self.run_task = None

    def _on_close(self):
        """Before 'close' event handler
        """

        if self.is_running():
            self._on_stop()
