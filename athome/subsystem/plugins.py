# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

import os
import sys
import logging

from athome.lib import pluginrunner, procsubsystem


LOGGER = logging.getLogger(__name__)


class Subsystem(procsubsystem.ProcSubsystem):
    """Subprocess subsystem"""

    def __init__(self, name):
        super().__init__(name, 'athome.lib.pluginrunner')

    def on_initialize(self, loop, config):
        super().on_initialize(loop, config)
        self.params = [config['pluginsdir'], str(config['plugin_poll_interval'])]

