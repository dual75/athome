# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

import logging

from athome.lib.procsubsystem import ProcSubsystem
from athome.lib.management import managed


LOGGER = logging.getLogger(__name__)


class TasksSubsystem(ProcSubsystem):
    """Subprocess subsystem"""

    def __init__(self, name):
        super().__init__(name, 'athome.lib.taskrunner')

    async def list_tasks(self):
        return await self.line_execute('list_tasks')

    list_tasks.managed = 'list_tasks'

