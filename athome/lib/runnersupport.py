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

from .procsubsystem import LINE_EXITED,\
    LINE_STARTED,\
    COMMAND_START,\
    COMMAND_CONFIG,\
    COMMAND_STOP

EXIT_OK=0
EXIT_ERROR=-1

LOGGER = logging.getLogger(__name__)


class RunnerSupport:

    def __init__(self, loop=None):
        self.events = asyncio.Queue()
        self.tasks = asyncio.Queue()
        self.pipe_stream = None
        self.line_protocol = None
        self.loop = loop or asyncio.get_event_loop()
        self.run_task = None
        self.config = None
        self.running = False
        
    def pipe_in(self, line):
        self.events.put_nowait(Message(MESSAGE_LINE, line))

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

    async def start_task(self):
        raise NotImplementedError

    async def stop_task(self):
        raise NotImplementedError
        
    async def _event_loop(self):
        while self.running or not self.events.empty():
            msg = await self.events.get()            
            if msg.type == MESSAGE_LINE:
                LOGGER.debug('got line %s', msg.value)
                command, arg = self.parse_line(msg.value)

                if command == COMMAND_START:
                    self.run_task = asyncio.ensure_future(
                        self.start_task(), 
                        loop=self.loop
                    )
                    self.pipe_out(LINE_STARTED)
                elif command == COMMAND_STOP:
                    self.running = False
                    await self.tasks.put(None)
                elif command == COMMAND_CONFIG:
                    self.config = arg
                else:
                    await self.on_command(command, arg)
        await self.stop_task()
        self.pipe_out(LINE_EXITED)

    async def on_command(self, command, arg):
        pass

    @staticmethod
    def parse_line(line):
        command, arg, chunks = line[:-1], None, line[:-1].split(' ', 1)
        if len(chunks) > 1:
            command, args = chunks[0], chunks[1]
            arg = json.loads(args)
        return command, arg


def runner_main(runner, debug=False):
    logging.basicConfig(level=debug and logging.DEBUG or logging.INFO)
    os.setpgid(os.getpid(), os.getpid())

    loop = asyncio.get_event_loop()
    loop.set_debug(debug)
    task = asyncio.ensure_future(runner.run())
    try:
        loop.run_until_complete(task)
        tasks = asyncio.Task.all_tasks()
        if tasks:
            for task in tasks:
                task.cancel()
            gather_task = asyncio.gather(*tasks, 
                loop=loop, 
                return_exceptions=True
            )
        loop.run_until_complete(gather_task)
        loop.close()
    except:
        LOGGER.exception('Error in runner')
        sys.exit(EXIT_ERROR)
    sys.exit(EXIT_OK)