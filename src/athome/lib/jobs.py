import asyncio
import logging
import sys
import traceback
import types

from contextlib import suppress
from async_timeout import timeout as atimeout

LOGGER = logging.getLogger(__name__)


class Job:

    _waited = False

    def __init__(self, coro, executor, callback=None, error_callback=None, cancelled_callback=None):
        assert coro is not None and asyncio.iscoroutine(coro)
        self.coro = coro
        self.executor = executor
        self._callback = callback
        self._error_callback = error_callback
        self._cancelled_callback = cancelled_callback
        self._traceback_stack = self._current_stack()
        self.job_task = asyncio.ensure_future(self._done_callback(coro), loop=self.executor.loop)

    async def _done_callback(self, coro):
        result = exc = None
        try:
            try:
                result = await coro
            except asyncio.CancelledError as ex:
                LOGGER.debug('task %s cancelled', self.job_task)
                if self._cancelled_callback:
                    self._cancelled_callback()
            except:
                _, exc, tb = sys.exc_info()
                self._traceback_stack = traceback.extract_tb(tb)
            finally:
                self.executor.discard(self)

            if not exc and self._callback:
                LOGGER.debug('invoking _callback')
                self._traceback_stack = self._current_stack()
                self._callback(result)
            elif exc and self._error_callback:
                LOGGER.debug('invoking _error_callback')
                self._error_callback(exc)
        except:
            LOGGER.warning('caught exception in callback')
            _, exc, tb = sys.exc_info()
            self._traceback_stack = traceback.extract_tb(tb)
        if exc:
            self._handle_exception(exc)
        
    @staticmethod
    def _current_stack():
        return traceback.extract_stack(sys._getframe(3))

    def _handle_exception(self, exc):
        exception_ctx = {
                'message': str(exc),
                'exception': exc,
                'future': self.job_task
        }
        if self.executor.loop.get_debug():
            exception_ctx['traceback'] = self._traceback_stack
        if self._waited:
            self.executor._handle_exception(exception_ctx)
        else:
            self.executor._failed_jobs.put_nowait(exception_ctx)

    async def wait(self, timeout=None):
        self._waited = True
        async with atimeout(timeout) as to:
            await self.job_task
            if to.expired:
                raise asyncio.TimeoutError()

    def cancel(self):
        if not self.job_task.done():
            self.job_task.cancel()
        self.executor.discard(self)

    def done(self):
        return self.job_task.done()

    def result(self):
        return self.job_task.result()

    def exception(self):
        return self.job_task.exception()

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

    def execute(self, coro, callback=None, error_callback=None, cancelled_callback=None):
        job = Job(coro, self, callback, error_callback, cancelled_callback)
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
            tbs = traceback.format_list(ctx['traceback'])
            sys.stderr.write(''.join(tbs))
        handler(ctx)

    def cancel(self):
        for job in list(self._in_execution):
            job.cancel()

    async def wait(self, timeout=None):
        gathered = asyncio.gather(*[job.job_task for job in self._in_execution], loop=self.loop)
        async with atimeout(timeout, loop=self.loop) as to:    
            await gathered
            if to.expired:
                raise asyncio.TimeoutError()


    async def close(self):
        self.cancel()
        await self._failed_jobs.put(None)
        await self._exception_task
