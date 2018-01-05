# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

import logging

from athome.subsystem import SubsystemModule

LOGGER = logging.getLogger(__name__)


class LoggingSubsystem(SubsystemModule):
    """Logging subsystem"""

    def __init__(self, name):
        super().__init__(name)
        self._logger = logging.getLogger()

    def on_initialize(self):
        """Perform subsystem initialization"""
        logging.config.dictConfig(self.config)

    def log(self, level , name, message, *params, **kwparams):
        logger = logging.getLogger(name)
        logger.log(level, message, *params, **kwparams)
    
    def debug(self, name, message, *params, **kwparams):
        self.log(logging.DEBUG, name, message, *params, **kwparams)

    def info(self, name, message, *params, **kwparams):
        self.log(logging.INFO, name, message, *params, **kwparams)

    def warning(self, name, message, *params, **kwparams):
        self.log(logging.WARNING, name, message, *params, **kwparams, exc_info=True)

    def error(self, name, message, *params, **kwparams):
        self.log(logging.ERROR, name, message, *params, **kwparams, exc_info=True)

