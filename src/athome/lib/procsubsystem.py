# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

import sys
import asyncio
import contextlib
import logging
import json

from athome.subsystem import SubsystemModule

LINE_EXITED = 'exit\n'
LINE_STARTED = 'started\n'
LINE_ERROR = 'error\n'

NEW_LINE = 10

COMMAND_START = 'start'

LOGGER = logging.getLogger(__name__)


def format_request(command, arg):
    message_arg = json.dumps(arg)
    return '{} {}'.format(command, message_arg)

def parse_request(line):
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

    @property   
    async def response(self):
        send_line(self.output_stream, format_request(self.command, self.arg))
        line = await input_stream.readline()
        return parse_request(line)



class ProcSubsystem(SubsystemModule):
    """Subprocess subsystem"""

    def __init__(self, name, module, params=list()):
        super().__init__(name)
        assert isinstance(params, (list, tuple))
        self.proc = None
        self.module = module
        self.params = params

    def on_start(self):
        self.executor.execute(self.run())

    def on_stop(self):
        """On 'stop' event callback method"""

        if self.proc:
            self.proc.terminate()

    def on_shutdown(self):
        """On 'shutdown' event callback method"""
        LOGGER.error("Shutdown!!!")
        if self.proc:
            LOGGER.error("Shutdown!!!")
            self.proc.kill()

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
                message_config = {
                    'env': self.env,
                    'subsystem_config': self.config
                }
                send_line(self.proc.stdin, format_request(COMMAND_START, message_config))

                while True:
                    data = await self.proc.stdout.readline()
                    if not data or data[-1] != NEW_LINE:
                        # EOF reached, partial reads are discarded
                        break
    
                    data = data.decode('utf-8')
                    if data == LINE_STARTED:
                        self.started()
            if self.proc.returncode is None:
                self.proc.kill()
            self.proc = None
            if self.is_stopping():
                self.stopped()
        except Exception as ex:
            LOGGER.exception('Exception occurred in run() coro')
            if self.proc:
                LOGGER.warning('Forcibly terminate process %s', self.proc)
                self.proc.kill()
            raise ex
    
    async def line_execute(self, command, arg=None):
        request = PipeRequest(command, arg, self.proc.stdout, self.proc.stdin)
        return await request.response

    def after_started(self):
        self.emit('{}_started'.format(self.name))

    def after_stopped(self):
        self.emit('{}_stopped'.format(self.name))



