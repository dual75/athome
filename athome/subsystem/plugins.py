# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

import sys
import asyncio
from asyncio import subprocess
import functools

from athome.lib import atprotocol, pluginrunner
from athome.submodule import SubsystemModule


class Subsystem(SubsystemModule):
    """Plugins subsystem"""

    def __init__(self, name, await_queue):
        super().__init__(name, await_queue)
        self.plugins = {}
        self.proc = None

    def on_stop(self):
        """On 'stop' event callback method"""

        for name in list(self.plugins.keys()):
            self.proc.communicate(pluginrunner.CODE_DEACTIVATE, name)
        self.plugins = None
        self.proc.terminate()
        self.proc = None

    def after_stop(self):
        self.core.emit('plugins_stopped')

    async def run(self):
        """Subsystem activity method

        This method is a *coroutine*.
        """

        #poll_interval = self.config['plugin_poll_interval']
        # self.core.emit('plugins_started')
        # with suppress(asyncio.CancelledError):
        self.proc = await asyncio.create_subprocess_exec(
            sys.executable, '-m', 'athome.lib.pluginrunner', self.config['plugindir'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            loop=self.loop)
        self.communicate(pluginrunner.CODE_ACTIVATE, 'ciao')
        await self.proc.wait()

    def communicate(self, code, payload):
        data = atprotocol.pack(code, payload)
        self.proc.communicate(data)


