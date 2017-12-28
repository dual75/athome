import asyncio
import logging
import sys
import traceback
import types

from contextlib import suppress
from async_timeout import timeout as atimeout

LOGGER = logging.getLogger(__name__)


class Job:

    def __init__(self, coro, executor, callback=None, error_callback=None, cancelled_callback=None):
        assert coro is not None and asyncio.iscoroutine(coro)
        self.coro = coro
        self.executor = executor
        self._success_callback = callback
        self._error_callback = error_callback
        self._cancelled_callback = cancelled_callback
        self._traceback_stack = self._current_stack()
        #self.job_task = asyncio.ensure_future(self._done_callback(coro), loop=self.executor.loop)
        self.job_task = executor.loop.create_task(coro)
        self.job_task.add_done_callback(self._done_callback)

    def _done_callback(self, future):
        self.executor.discard(self)
        try:
            exc = future.exception()
        except asyncio.CancelledError as ce:
            if self._cancelled_callback:
                self._cancelled_callback()
        else:
            if exc:
                self._traceback_stack = exc.__traceback__
                self._handle_exception(exc)
                if self._error_callback:
                    self._error_callback(exc)
            elif self._success_callback:
                self._success_callback(future.result())
        finally:
            self.executor = None

    '''
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
    '''
        
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
        self.executor._handle_exception(exception_ctx)

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

    def _handle_exception(self, ctx):
        handler = self.exception_handler\
                    or self.loop.get_exception_handler()\
                    or self.loop.default_exception_handler
        LOGGER.debug('_handle_exception, handler is %s', handler)
        if self.loop.get_debug():
            traceback.print_tb(ctx['traceback'])
        handler(ctx)

    def cancel(self):
        for job in list(self._in_execution):
            job.cancel()

    async def wait(self, timeout=None):
        gathered = asyncio.gather(*[job.job_task for job in self._in_execution], 
            loop=self.loop,
            return_exceptions=True)
        async with atimeout(timeout, loop=self.loop) as to:    
            await gathered
            if to.expired:
                raise asyncio.TimeoutError()
