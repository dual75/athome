# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

import sys
import asyncio
import logging
import signal
from asyncio import subprocess
import functools

from athome.lib import pluginrunner
from athome.submodule import SubsystemModule


LOGGER = logging.getLogger(__name__)


class Subsystem(SubsystemModule):
    """Plugins subsystem"""

    def __init__(self, name, await_queue):
        super().__init__(name, await_queue)
        print('plugins!!')
        self.proc = None

    def on_stop(self):
        """On 'stop' event callback method"""

        self.proc.communicate('stop')

    def after_stop(self):
        self.core.emit('plugins_stopped')

    async def run(self):
        """Subsystem activity method

        This method is a *coroutine*.
        """

        print('diocaneeeee-')
        self.proc = await asyncio.create_subprocess_exec(
            sys.executable, '-m', 'athome.lib.pluginrunner', self.config['plugindir'], "5", 
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            loop=self.loop)
        self.communicate('start')
        data = 'start'
        while data != 'exit\n':
            data = await self.proc.stdout.readline()
        await self.proc.wait()
        self.proc = None

    def communicate(self, payload):
        self.proc.communicate(payload.encode('utf-8') + b'\n')


def stop(s):
    LOGGER.info('send stop')
    sub.communicate('stop')


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
    loop = asyncio.get_event_loop()
    queue = asyncio.Queue()
    s = Subsystem('plugins', queue)
    s.initialize(loop, {'plugindir':'plugindir'})
    install_signal_handlers(loop, s)
    run_task = asyncio.ensure_future(s.run())
    loop.run_until_complete(run_task)
    loop.close()


if __name__ == '__main__':
    main()


