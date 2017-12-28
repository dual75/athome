# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

import os
import sys
import json
import logging
import asyncio
import signal
from functools import partial

import athome
from athome import Message, MESSAGE_SHUTDOWN, MESSAGE_LINE
from athome.lib.lineprotocol import LineProtocol
from athome.lib.jobs import Executor

from .procsubsystem import COMMAND_START, \
    LINE_STARTED,\
    LINE_READY,\
    send_line,\
    parse_line,\
    format_line


LOGGER = logging.getLogger(__name__)


class RunnerSupport:

    def __init__(self, name, loop=None):
        assert name is not None
        self.name = name
        self.loop = loop or asyncio.get_event_loop()
        self.messages = asyncio.Queue()
        self.pipe_stream = None
        self.line_protocol = None
        self.env = None
        self.config = None
        self.executor = Executor(loop=self.loop)
        for signame in 'SIGINT', 'SIGTERM':
            self.loop.add_signal_handler(
                getattr(signal, signame), 
                partial(self.handle_stop_signal, signame)
                )
        
    def pipe_in(self, line):
        self.messages.put_nowait(Message(MESSAGE_LINE, line, None))

    def pipe_out(self, str_):
        self.pipe_stream.write(str_.encode('utf-8'))

    async def run(self):
        _, self.line_protocol = await self.loop.connect_read_pipe(
            lambda: LineProtocol(self.pipe_in), 
            sys.stdin
        )
        self.pipe_stream, _ = await self.loop.connect_write_pipe(
            asyncio.BaseProtocol,
            sys.stdout
        )
        self.running = True
        self.pipe_out(LINE_READY)
        await self._event_loop()

    async def run_coro(self):
        raise NotImplementedError

    async def term_coro(self):
        pass

    def _error_callback(self, exc):
        print("#### Now calling _error_callback on exc %s ####" % exc)
        self.outcome = LINE_ERROR
        self.running = False
        self.messages.put_nowait(Message(MESSAGE_SHUTDOWN, None))
        
    async def _event_loop(self):
        try:
            while self.running or not self.messages.empty():
                msg = await self.messages.get()            
                if msg.type == MESSAGE_LINE:
                    LOGGER.debug('got line %s', msg.value)
                    command, arg = parse_line(msg.value)


                    if arg and '__request_uuid' in arg:
                        handler = getattr(self, '{}_request_handler'.format(command), None)
                        assert asyncio.iscoroutinefunction(handler)
                        response = {
                            '__request_uuid': arg['__request_uuid']
                        }
                        data = await handler(arg)
                        response['payload'] = data
                        self.pipe_out(format_line('response', data))
                    else:   
                        handler = getattr(self, '{}_line_handler'.format(command), None)
                        if handler:
                            assert asyncio.iscoroutinefunction(handler)
                            LOGGER.debug('invoking line handler %s', handler)
                            await handler(arg)
        finally:
            self._remove_pid_file()

    async def start_line_handler(self, arg):
        self.env = arg['env']
        self.config = arg['subsystem_config']
        self._write_pid_file()
        self.executor.execute(self.run_coro())
        self.pipe_out(LINE_STARTED)

    def handle_stop_signal(self, signame):
        self.running = False

    async def on_input_line(self, command, arg):
        pass

    def _pid_file(self):
        return os.path.join(self.env['run_dir'], '{}_subsystem.pid'.format(self.name))

    def _write_pid_file(self):
        with open(self._pid_file(), 'w') as file_out:
            file_out.write('{}'.format(os.getpid()))
    
    def _remove_pid_file(self):
        fname = self._pid_file()
        if os.path.exits(fname) and os.access(fname, os.W_OK):
            os.unlink(fname)


def runner_main(runner, debug=False):
    logging.basicConfig(level=debug and logging.DEBUG or logging.INFO)
    os.setpgid(os.getpid(), os.getpid())

    loop = asyncio.get_event_loop()
    loop.set_debug(debug)
    task = asyncio.ensure_future(runner.run())
    try:
        loop.run_until_complete(task)
        loop.close()
    except:
        LOGGER.exception('Error in runner')
        sys.exit(athome.PROCESS_OUTCOME_KO)
    sys.exit(athome.PROCESS_OUTCOME_KO)
    