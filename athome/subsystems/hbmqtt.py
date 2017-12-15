# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

import json

from athome.lib.procsubsystem import ProcSubsystem


class Subsystem(ProcSubsystem):
    """Subprocess subsystem"""

    def __init__(self, name):
        super().__init__(name, 'athome.lib.hbmqttrunner')

    def on_initialize(self):
        self.params = [ json.dumps(self.config) ]


