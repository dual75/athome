# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

import os
import sys
import logging

from athome.lib.procsubsystem import ProcSubsystem


LOGGER = logging.getLogger(__name__)


class Subsystem(ProcSubsystem):
    """Subprocess subsystem"""

    def __init__(self, name):
        super().__init__(name, 'athome.lib.pluginrunner')

    def on_initialize(self):
        super().on_initialize()
        self.params = [ 
            self.config['plugins_dir'], 
            str(self.config['plugin_poll_interval'])
            ]

