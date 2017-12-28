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

from athome.subsystem import SubsystemModule

LINE_READY = 'ready\n'
LINE_EXITED = 'exit\n'
LINE_STARTED = 'started\n'
LINE_ERROR = 'error\n'

NEW_LINE = 10

COMMAND_START = 'start'

LOGGER = logging.getLogger(__name__)


def format_line(command, arg):
    message_arg = json.dumps(arg)
    return '{} {}'.format(command, message_arg)

def parse_line(line):
    command, arg, chunks = line[:-1], None, line[:-1].split(' ', 1)
    if len(chunks) > 1:
        command, args = chunks[0], chunks[1]
        arg = json.loads(args)
    return command, arg

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

                data = await self.readline()
                if data != LINE_READY:
                    raise AssertionError("first expected line from child MUST be 'ready', was \'{}\'".format(data))

                # initialize subprocess runner
                message_config = {'env': self.env, 'subsystem_config': self.config}
                self.sendline(COMMAND_START, message_config)

                while True:
                    line = await self.readline()
                    if not line:
                        break
    
                    command, arg = parse_line(line)
                    handler_coro = getattr(self, '{}_line_handler'.format(command), None)
                    if handler_coro:
                        assert asyncio.iscoroutinefunction(handler_coro)
                        await handler_coro(arg)

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

    async def response_line_handler(self, arg):
        res_id = arg['__request_uuid']
        assert self.request and not self.request.done()
        self.request.set_result(arg)

    async def readline(self):
        result = None
        data = await self.proc.stdout.readline()
        if data and data[-1] == NEW_LINE:
            result = data.decode('utf-8')
        return result

    def sendline(self, request, arg=None):
        send_line(self.proc.stdin, format_line(request, arg))

    async def line_execute(self, command, arg=dict(), callback=None):
        assert self.request is None
        self.request = self.loop.create_future()
        reqid = uuid.uuid4().hex
        arg['__request_uuid'] = reqid
        self.sendline(command, arg)
        await self.request
        result = self.request.get_result()
        assert result['__request_uuid'] == reqid
        self.request = None
        return result['payload']

    def after_started(self):
        self.emit('{}_started'.format(self.name))

    def after_stopped(self):
        self.emit('{}_stopped'.format(self.name))



