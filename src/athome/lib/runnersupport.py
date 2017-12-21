# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

import os
import sys
import json
import logging
import asyncio

from athome import Message, MESSAGE_LINE
from athome.lib.lineprotocol import LineProtocol
from athome.lib.jobs import Executor

from .procsubsystem import LINE_EXITED,\
    LINE_STARTED,\
    COMMAND_START,\
    COMMAND_CONFIG,\
    COMMAND_STOP

EXIT_OK=0
EXIT_ERROR=-1

LOGGER = logging.getLogger(__name__)


class RunnerSupport:

    def __init__(self, name, loop=None):
        self.name = name
        self.loop = loop or asyncio.get_event_loop()
        self.messages = asyncio.Queue()
        self.pipe_stream = None
        self.line_protocol = None
        self.run_job = None
        self.env = None
        self.config = None
        self.running = False
        self.executor = Executor(loop=self.loop)
        
    def pipe_in(self, line):
        self.messages.put_nowait(Message(MESSAGE_LINE, line))

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
        await self._event_loop()

    async def run_coro(self):
        raise NotImplementedError
        
    async def _event_loop(self):
        while self.running or not self.messages.empty():
            msg = await self.messages.get()            
            if msg.type == MESSAGE_LINE:
                LOGGER.debug('got line %s', msg.value)
                command, arg = self._parse_line(msg.value)
                if command == COMMAND_START:
                    self.run_job = self.executor.execute(self.run_coro())
                    self.pipe_out(LINE_STARTED)
                elif command == COMMAND_STOP:
                    self.running = False
                elif command == COMMAND_CONFIG:
                    self.env = arg['env']
                    self.config = arg['subsystem_config']
                    self._write_pid_file()
                else:
                    await self.on_command(command, arg)
        await self.executor.cancel_all()
        self.pipe_out(LINE_EXITED)
        self._remove_pid_file()

    async def on_command(self, command, arg):
        pass

    @staticmethod
    def _parse_line(line):
        command, arg, chunks = line[:-1], None, line[:-1].split(' ', 1)
        if len(chunks) > 1:
            command, args = chunks[0], chunks[1]
            arg = json.loads(args)
        return command, arg

    def _pid_file(self):
        return os.path.join(
            self.env['run_dir'], 
            '{}_subsystem.pid'.format(self.name)
        )

    def _write_pid_file(self):
        with open(self._pid_file(), 'w') as file_out:
            file_out.write('{}'.format(os.getpid()))
    
    def _remove_pid_file(self):
        os.unlink(self._pid_file())


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
        sys.exit(EXIT_ERROR)
    sys.exit(EXIT_OK)