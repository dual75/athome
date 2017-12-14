# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

import os
import sys
import logging
import json

from athome.lib import pluginrunner, procsubsystem


LOGGER = logging.getLogger(__name__)


class Subsystem(procsubsystem.ProcSubsystem):
    """Subprocess subsystem"""

    def __init__(self, name):
        super().__init__(name, 'athome.lib.hbmqttrunner')

    def on_initialize(self):
        self.params = [ json.dumps(self.config) ]


