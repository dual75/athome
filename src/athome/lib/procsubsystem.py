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

COMMAND_START = 'start'

LOGGER = logging.getLogger(__name__)


def format_request(self, command, arg):
    message_arg = json.dumps(arg)
    return '{} {}'.format(COMMAND_START, json.dumps(message_config))


def send_line(self, stream, payload):
    stream.write((payload + '\n').encode('utf-8'))


@staticmethod
def parse_line(line):
    command, arg, chunks = line[:-1], None, line[:-1].split(' ', 1)
    if len(chunks) > 1:
        command, args = chunks[0], chunks[1]
        arg = json.loads(args)
    return command, arg


class PipeRequest:
    def __init__(self, command, arg, input_stream, output_stream):
        self.command = command
        self.arg = arg
        self.input_stream = input_stream
        self.output_stream = output_stream

    @property   
    async def response(self):
        send_line(self.output_stream, self.command, json.dumps(self.arg))
        line = await input_stream.readline()



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
        if self.proc:
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
                    'env': self.,
                    'subsystem_config': self.config
                }
                await self.line_execute(COMMAND_START, message_config)

                while True:
                    data = await self.proc.stdout.readline()
                    if not data:
                        # EOF reached, pipe closed
                        break
    
                    data = data.decode('utf-8')
                    if data == LINE_STARTED:
                        self.started()
            if self.proc.returncode is None:
                self.proc.kill()
            self.proc = None
            if not self.state in 'closed', 'failed':
                self.stopped()
        except Exception as ex:
            LOGGER.exception('Exception occurred in run() coro')
            if self.proc:
                LOGGER.warning('Forcibly terminate process %s', self.proc)
                self.proc.kill()
            raise ex
    
    async def line_execute(self, command, arg=None):
        request = PipeRequest(command, arg, self.proc, self.proc)
        return await request.response

    async def handle_log(self, value):
        pass

    def after_started(self):
        self.emit('{}_started'.format(self.name))

    def after_stopped(self):
        self.emit('{}_stopped'.format(self.name))



