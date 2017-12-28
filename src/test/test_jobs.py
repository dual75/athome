# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

"""
"""

import asyncio
import os
import unittest
from functools import partial
from contextlib import suppress
from test import common

from athome.lib import jobs


async def simple_success():
    await asyncio.sleep(1)
    return 'success'

async def simple_error():
    return 1 / 0

async def simple_long():
    await asyncio.sleep(2)

def cb(d, *arg):
    d['outcome'] = 'called'


class JobsTest(common.AsyncTest):
    """Test mqtt client"""

    def setUp(self):
        super().setUp()

    def tearDown(self):
        super().tearDown()

    def test_run_success(self):
        executor = jobs.Executor()
        executor.execute(simple_success())
        self.complete(executor.wait())
        self.assertFalse(executor._in_execution)

    def test_callback_success(self):
        executor = jobs.Executor()
        d = {}
        executor.execute(simple_success(), partial(cb, d))
        self.complete(executor.wait())
        self.assertTrue(d)

    def test_callback_error(self):
        executor = jobs.Executor()
        d = {}
        executor.execute(simple_error(), None, partial(cb, d))
        self.complete(executor.wait())
        self.assertTrue(d)

    def test_create_loop(self):
        executor1 = jobs.Executor(loop=self.loop)
        executor2 = jobs.Executor()
        self.assertIs(executor1.loop, executor2.loop)

    def test_callback_cancelled(self):
        executor = jobs.Executor()
        d = {}
        async def ww():
            job = executor.execute(simple_long(), None, None, partial(cb, d))
            await asyncio.sleep(0.1)
            job.cancel()
            await asyncio.sleep(0.1)
        self.complete(ww())
        self.assertTrue(d)

    def test_executor_cancel(self):
        executor = jobs.Executor()
        async def w():
            executor.execute(simple_long())
            executor.execute(simple_long())
            await asyncio.sleep(0.5)
            executor.cancel()
            self.assertFalse(executor._in_execution)
        self.complete(w())

    def test_executor_wait_timeout(self):
        executor = jobs.Executor()
        async def w():
            executor.execute(simple_long())
            await executor.wait()
        
        self.complete(w())

    def test_executor_wait_timeout_error(self):
        executor = jobs.Executor()
        async def w():
            executor.execute(asyncio.sleep(20))
            await executor.wait(0.1)
        
        with self.assertRaises(asyncio.TimeoutError):
                self.complete(w())
        
        
if __name__ == '__main__':
    unittest.main()
