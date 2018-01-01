# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

import asyncio
import contextlib
import json
import logging
import os
import sys
import types
import uuid

from athome.lib.lineprotocol import Line, LineProtocol, decode_line, encode_line, LINE_START, NEW_LINE
from athome.subsystem import SubsystemModule
from athome import Message, MESSAGE_LINE

LOGGER = logging.getLogger(__name__)


class ProcSubsystem(SubsystemModule):
    """Subprocess subsystem"""

    def __init__(self, name, module, params=list()):
        super().__init__(name)
        assert isinstance(params, (list, tuple))
        self.module = module
        self.params = params
        self.current_request = None
        self._transport = None
        self._protocol = None
        self._req_semaphore = asyncio.Semaphore()

    def on_start(self):
        self.executor.execute(self._coro_start())
    
    async def _coro_start(self):
        params = [sys.executable, '-m', self.module] + self.params
        self._transport, self._protocol = await self.loop.subprocess_exec(
            lambda: LineProtocol(self.pipe_in, self._handle_process_exit),
            *params,
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE)
        
        self._write_pid_file()

        # initialize subprocess runner
        message_config = {'env': self.env, 'subsystem_config': self.config}
        self.sendline(LINE_START, payload=message_config)

    def on_stop(self):
        """On 'stop' event callback method"""

        if self._transport:
            self._transport.terminate()

    def on_shutdown(self):
        """On 'shutdown' event callback method"""

        if not self._transport.get_returncode():
            LOGGER.error("now killing self.subprocess")
            self._transport.kill()
            self._transport = None

    async def on_message(self, msg):
        await super().on_message(msg)
        if msg.type == MESSAGE_LINE:
            if not msg.data:
                if self.is_stopping():
                    self.stopped()
            else:
                await self._handle_line(msg.value)
    
    async def _handle_line(self, line):
        handler_coro = getattr(self, '{}_line_handler'.format(line.message), None)
        if handler_coro:
            assert asyncio.iscoroutinefunction(handler_coro)
            await handler_coro(line.payload)
    
    def _handle_process_exit(self):
        LOGGER.info("subprocess %s, exited", self.name)
        self._remove_pid_file()
        self._transport = None

    async def started_line_handler(self, arg):
        self.started()

    async def response_line_handler(self, payload):
        assert self.current_request and not self.current_request.done()
        if 'error' in payload:
            self.current_request.set_exception(Exception(payload['error_message']))
        else:
            self.current_request.set_result(payload['response'])

    def pipe_in(self, line):
        self.message_queue.put_nowait(Message(MESSAGE_LINE, line, None))

    def sendline(self, message, payload=None, req_id=None):
        self._transport.get_pipe_transport(0).write(encode_line(Line(req_id, message, payload)))

    async def line_execute(self, command, payload=None, callback=None):
        result = None
        await self._req_semaphore.acquire()
        try:
            assert self.current_request is None
            self.current_request = self.loop.create_future()
            req_id = uuid.uuid4().hex
            self.sendline(command, payload=payload, req_id=req_id)
            result = await self.current_request
            self.current_request = None
            return result
        finally:
            self._req_semaphore.release()
        return result

    def after_started(self):
        self.emit('{}_started'.format(self.name))

    def after_stopped(self):
        self.emit('{}_stopped'.format(self.name))

    def _pid_file(self):
        return os.path.join(self.env['run_dir'], '{}_subsystem.pid'.format(self.name))

    def _write_pid_file(self):
        with open(self._pid_file(), 'w') as file_out:
            file_out.write('{}'.format(self._transport.get_pid()))
    
    def _remove_pid_file(self):
        fname = self._pid_file()
        if os.path.exists(fname) and os.access(fname, os.W_OK):
            os.unlink(fname)
