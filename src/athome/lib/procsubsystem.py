# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

import sys
import asyncio
import contextlib
import logging
import json
import types
import uuid

from collections import namedtuple

from athome.subsystem import SubsystemModule

Line = namedtuple('Line', ('req_id', 'message', 'payload'))

LINE_READY = 'ready'
LINE_EXITED = 'exit'
LINE_STARTED = 'started'
LINE_ERROR = 'error'

NEW_LINE = 10

COMMAND_START = 'start'

LOGGER = logging.getLogger(__name__)


def format_line(line):
    message = {
        'req_id': line.req_id,
        'message': line.message,
        'payload': line.payload
        }
    return json.dumps(message)

def parse_line(line):
    message = json.loads(line)
    return Line(message['req_id'], message['message'], message['payload'])

def send_line(stream, payload):
    stream.write((payload + '\n').encode('utf-8'))

class PipeRequest:
    def __init__(self, command, arg, input_stream, output_stream):
        self.command = command
        self.arg = arg
        self.input_stream = input_stream
        self.output_stream = output_stream
   
    async def response(self):
        send_line(self.output_stream, format_line(self.command, self.arg))
        response_line = await self.input_stream.readline()
        return parse_line(response_line)


class ProcSubsystem(SubsystemModule):
    """Subprocess subsystem"""

    def __init__(self, name, module, params=list()):
        super().__init__(name)
        assert isinstance(params, (list, tuple))
        self.proc = None
        self.module = module
        self.params = params
        self.request = None
        self.req_semaphore = asyncio.Semaphore()

    def on_start(self):
        self.executor.execute(self.run())

    def on_stop(self):
        """On 'stop' event callback method"""

        if self.proc:
            self.proc.terminate()

    def on_shutdown(self):
        """On 'shutdown' event callback method"""
        if self.proc:
            LOGGER.error("now killing self.proc")
            self.proc.kill()
            self.proc = None

    async def run(self):
        """Subsystem activity method

        This method is a *coroutine*.
        """
        try:
            params = [sys.executable, '-m', self.module] + self.params
            with contextlib.suppress(asyncio.CancelledError):
                self.proc = await asyncio.create_subprocess_exec(*params, 
                    stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                    loop=self.loop)

                # initialize subprocess runner
                message_config = {'env': self.env, 'subsystem_config': self.config}
                self.sendline(COMMAND_START, payload=message_config)

                while True:
                    line = await self.readline()
                    if not line:
                        break
    
                    handler_coro = getattr(self, '{}_line_handler'.format(line.message), None)
                    if handler_coro:
                        assert asyncio.iscoroutinefunction(handler_coro)
                        await handler_coro(line.payload)

            if self.proc.returncode is None:
                self.proc.kill()
            self.proc = None
            if self.is_stopping():
                self.stopped()
        except:
            LOGGER.exception('Exception occurred in run() coro')
            if self.proc:
                LOGGER.warning('Forcibly terminate process %s', self.proc)
                self.proc.kill()
            raise

    async def started_line_handler(self, arg):
        self.started()

    async def response_line_handler(self, payload):
        assert self.request and not self.request.done()
        self.request.set_result(payload)

    async def readline(self):
        result = None
        data = await self.proc.stdout.readline()
        if data and data[-1] == NEW_LINE:
            sdata = data.decode('utf-8')
            result = parse_line(sdata)
        return result

    def sendline(self, message, payload=None, req_id=None):
        send_line(self.proc.stdin, format_line(Line(req_id, message, payload)))

    async def line_execute(self, command, payload=None, callback=None):
        result = None
        await self.req_semaphore.acquire()
        try:
            assert self.request is None
            self.request = self.loop.create_future()
            req_id = uuid.uuid4().hex
            self.sendline(command, payload=payload, req_id=req_id)
            result = await self.request
            self.request = None
            return result
        finally:
            self.req_semaphore.release()
        return result

    def after_started(self):
        self.emit('{}_started'.format(self.name))

    def after_stopped(self):
        self.emit('{}_stopped'.format(self.name))



