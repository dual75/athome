# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

import os
import sys
import asyncio
import logging
import json

from hbmqtt.broker import Broker

from athome import Message, MESSAGE_LINE
from athome.lib.lineprotocol import LineProtocol

LOGGER = logging.getLogger(__name__)

class Runner:
    """Hbmqtt broker runner"""

    def __init__(self, config):
        self.broker = None
        self.config = config
        self.events = asyncio.Queue()
        self.running = False
       
    def pipe_in(self, line):
        LOGGER.info('protocol yieled line: %s', line)
        self.events.put_nowait(Message(MESSAGE_LINE, line[:-1]))
        self.pipe_out(line)

    def pipe_out(self, str_):
        self.pipe_stream.write((str_ + '\n').encode('utf-8'))

    async def run(self):
        self.broker = Broker(self.config)
        loop = asyncio.get_event_loop()
        _, protocol = await loop.connect_read_pipe(
            lambda: LineProtocol(self.pipe_in), 
            sys.stdin
        )
        self.pipe_stream, _ = await loop.connect_write_pipe(
            asyncio.BaseProtocol,
            sys.stdout
        )
        await self.broker.start()
        self.pipe_out('started')
        self.running = True
        await self._event_loop()
        
    async def _event_loop(self):
        while self.running or not self.events.empty():
            msg = await self.events.get()
            LOGGER.info('Runner got msg %s: %s', msg.type, msg.value)
            
            if msg.type == MESSAGE_LINE:
                LOGGER.debug('got event %s', msg.value)
                command, arg = self.parseLine(msg.value)
                if command == 'stop':
                    self.running = False
                elif command == 'config':
                    pass
        self.pipe_out('exit')

    def parseLine(self, line):
        command, arg, chunks = line, None, line.split(' ', 1)
        if len(chunks) > 1:
            command, args = chunks[0], chunks[1]
            arg = json.loads(args)
        return command, arg


def main():
    logging.basicConfig(level=logging.DEBUG)
    os.setpgid(os.getpid(), os.getpid())

    loop = asyncio.get_event_loop()
    loop.set_debug(True)
    runner = Runner(json.loads(sys.argv[1]))
    task = asyncio.ensure_future(runner.run())
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
    sys.exit(0)


if __name__ == '__main__':
    main()
