# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

__all__ = ['core', 'module']

from collections import namedtuple

MESSAGE_AWAIT, MESSAGE_EVT, MESSAGE_START, MESSAGE_STOP, MESSAGE_RESTART = range(5)
Message = namedtuple('Message', ('type', 'value'))


