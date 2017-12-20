import sys

import asyncio
import traceback
import logging

from collections import deque
from functools import partial
from contextlib import suppress

from async_timeout import timeout as atimeout

LOGGER = logging.getLogger(__name__)


class Job:

    _waited = False

    def __init__(self, coro, executor, callback=None, error_callback=None):
        self.coro = coro
        self.executor = executor
        self._callback = callback
        self._error_callback = error_callback
        self._traceback_stack = self._current_stack()
        self.run_task = task = executor.loop.create_task(coro)
        task.add_done_callback(self._done_callback)

    def _done_callback(self, future):
        self.executor.discard(self)
        try:
            exc = future.exception()
            if not exc:
                if self._callback:
                    try:
                        self._traceback_stack = self._current_stack()
                        self._callback(future.result())
                    except Exception as e:
                        LOGGER.warning('caught exception in done callback')
                        exc = e
                        self._traceback_stack = traceback.extract_tb(sys.exc_info()[2])
            elif self._error_callback:
                try:
                    self._traceback_stack = self._current_stack()
                    self._error_callback(exc)
                    exc = None
                except Exception as e:
                    LOGGER.warning('caught exception in error callback')
                    exc = e
                    self._traceback_stack = traceback.extract_tb(sys.exc_info()[2])
            if exc:
                self._handle_exception(exc)
        except asyncio.CancelledError:
            LOGGER.debug('Task %s cancelled', self.run_task)

    @staticmethod
    def _current_stack():
        return traceback.extract_stack(sys._getframe(3))

    def _handle_exception(self, exc):
        exception_ctx = {
                'message': str(exc),
                'exception': exc,
                'future': self.run_task
        }
        if self.executor.loop.get_debug():
            exception_ctx['traceback'] = self._traceback_stack
        if self._waited:
            self.executor._handle_exception(exception_ctx)
        else:
            self.executor._failed_jobs.put_nowait(exception_ctx)

    async def wait(self, timeout=-1):
        self._waited = True
        with atimeout(timeout):
            await self.run_task

    def close(self):
        if not self.run_task.done():
            self.run_task.cancel()
        self.executor.discard(self)

    def done(self):
        return self.run_task.done()

    def result(self):
        return self.run_task.result()

    def exception(self):
        return self.run_task.exception()

    @property
    def callback(self):
        return self._callback

    @property
    def error_callback(self):
        return self._error_callback


class Executor:

    def __init__(self, loop=None, exception_handler=None):
        self.loop = loop or asyncio.get_event_loop()
        self.exception_handler = exception_handler
        self._exception_task = self.loop.create_task(self._exception_loop())
        self._in_execution = set()
        self._failed_jobs = asyncio.Queue()

    def __contains__(self, item):
        return item in self._in_execution

    def discard(self, task):
        self._in_execution.discard(task)

    def execute(self, coro, callback=None, error_callback=None):
        job = Job(coro, self, callback, error_callback)
        self._in_execution.add(job)
        return job
    
    async def _exception_loop(self):
        while True:
            ctx = await self._failed_jobs.get()
            if ctx is None:
                break
            try:
               self._handle_exception(ctx)
            except:
                LOGGER.error('error while invoking exception_handler')

    def _handle_exception(self, ctx):
        handler = self.exception_handler\
                    or self.loop.get_exception_handler()\
                    or self.loop.default_exception_handler
        LOGGER.debug('_handle_exception, handler is %s', handler)
        if self.loop.get_debug():
            LOGGER.debug('writing out traceback: %s', ctx['traceback'])
            tbs = traceback.format_list(ctx['traceback'])
            sys.stderr.write(''.join(tbs))
        handler(ctx)

    async def close(self):
        for job in list(self._in_execution):
            job.close()
        await self._failed_jobs.put(None)
        await asyncio.gather(
            #self._await_task,
            self._exception_task,
            loop=self.loop
        )

async def test():
    print('cisono')


def done(future):
    a = 1 / 0
    print(future)


async def main():
    executor = Executor()
    job = executor.execute(test(), done)
    await asyncio.sleep(1)
    await executor.close()
    

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    loop = asyncio.get_event_loop()
    loop.set_debug(False)
    asyncio.get_event_loop().run_until_complete(main())