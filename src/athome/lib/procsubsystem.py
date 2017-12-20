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
COMMAND_STOP = 'stop'
COMMAND_CONFIG = 'config'

LOGGER = logging.getLogger(__name__)


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

        self.executor.execute(self.send_line(COMMAND_STOP))

    def on_shutdown(self):
        """On 'shutdown' event callback method"""

        self.executor.execute(self.send_line(COMMAND_STOP))

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
                await self.send_line('{} {}'.format(COMMAND_CONFIG, json.dumps(message_config)))

                # start sub process runner
                await self.send_line(COMMAND_START)

                running = True
                while running:
                    data = await self.proc.stdout.readline()
                    if not data:
                        # EOF reached, pipe closed
                        break
    
                    data = data.decode('utf-8')
                    if data == LINE_STARTED:
                        self.started()
                    elif data == LINE_EXITED:
                        running = False
            await self.proc.wait()
            self.proc = None
            if not self.is_closed():
                self.stopped()
        except Exception as ex:
            LOGGER.exception('Exception occurred in run() coro')
            if self.proc:
                LOGGER.warning('Forcibly terminate process %s', self.proc)
                self.proc.kill()
            raise ex

    def after_started(self):
        self.emit('{}_started'.format(self.name))

    def after_stopped(self):
        self.emit('{}_stopped'.format(self.name))

    async def send_line(self, payload):
        self.proc.stdin.write((payload + '\n').encode('utf-8'))

