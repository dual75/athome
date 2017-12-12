# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

import os
import sys
import asyncio
import contextlib
import logging
import signal
from asyncio import subprocess
import functools

from athome import Message, MESSAGE_AWAIT, MESSAGE_EVT
from athome.lib import pluginrunner
from athome.submodule import SubsystemModule


LOGGER = logging.getLogger(__name__)


class Subsystem(SubsystemModule):
    """Plugins subsystem"""

    def __init__(self, name, event_queue):
        super().__init__(name, event_queue)
        self.proc = None

    def on_stop(self):
        """On 'stop' event callback method"""

        self.core.faf(self.sendLine('stop'))

    async def run(self):
        """Subsystem activity method

        This method is a *coroutine*.
        """

        with contextlib.suppress(asyncio.CancelledError):
            self.proc = await asyncio.create_subprocess_exec(
                sys.executable, '-m', 
                'athome.lib.pluginrunner', self.config['plugins_dir'], "5", 
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                loop=self.loop)
            
            running = True
            while running:
                data = await self.proc.stdout.readline()
                if not data:
                    # EOF reached, pipe closed
                    break
     
                data = data[:-1].decode('utf-8')
                LOGGER.info('plugins subsystem got line: %s', data)
                if data == 'exit':
                    running = False
                
            await self.proc.wait()
        self.proc = None
        self.stopped()

    def after_stopped(self):
        self.core.emit('plugins_stopped'))

    async def sendLine(self, payload):
        await self.proc.communicate((payload + '\n').encode('utf-8'))
        LOGGER.info('sent line %s', payload)


def stop(s):
    LOGGER.info('send stop')
    s.stop()


def install_signal_handlers(loop, sub):
    """Install signal handlers for SIGINT and SIGTERM

    Parameters:
    param:
    """

    signames = ('SIGINT', 'SIGTERM')
    if sys.platform != 'win32':
        for signame in signames:
            loop.add_signal_handler(getattr(signal, signame),
                                    functools.partial(stop, sub))

def main():
    logging.basicConfig(level=logging.DEBUG)
    loop = asyncio.get_event_loop()
    queue = asyncio.Queue()
    s = Subsystem('plugins', queue)
    s.initialize(loop, {'plugins_dir':'tmp'})
    install_signal_handlers(loop, s)
    s.start()
    try:
        loop.run_until_complete(s.run_task)
        loop.stop()
    finally:
        pass


if __name__ == '__main__':
    main()


