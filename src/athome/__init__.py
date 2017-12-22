# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.
"""
__init__.py module for 'athome' package
"""

__all__ = [
    'core',
    'system',
    'subsystem'
]

from collections import namedtuple

MESSAGE_EVT, \
MESSAGE_START, \
MESSAGE_STOP, \
MESSAGE_SHUTDOWN, \
MESSAGE_LINE, \
MESSAGE_NONE = range(6)

Message = namedtuple('Message', ('type', 'value', 'data'))
