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

from athome.lib import pluginrunner
from athome.submodule import SubsystemModule


LOGGER = logging.getLogger(__name__)


class ProcSubsystem(SubsystemModule):
    """Subprocess subsystem"""

    def __init__(self, name, module, params=list()):
        super().__init__(name)
        assert isinstance(params, (list, tuple))
        self.proc = None
        self.module = module
        self.params = params

    def on_stop(self):
        """On 'stop' event callback method"""

        self.core.faf(self.sendLine('stop'))

    async def run(self):
        """Subsystem activity method

        This method is a *coroutine*.
        """

        params = [sys.executable, '-m', self.module] + self.params 
        with contextlib.suppress(asyncio.CancelledError):
            self.proc = await asyncio.create_subprocess_exec(
                *params,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                loop=self.loop)
            
            self.started()
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

    def after_started(self):
        self.core.emit('{}_started'.format(self.name))

    def after_stopped(self):
        self.core.emit('{}_stopped'.format(self.name))

    async def sendLine(self, payload):
        await self.proc.communicate((payload + '\n').encode('utf-8'))
        LOGGER.info('sent line %s', payload)


