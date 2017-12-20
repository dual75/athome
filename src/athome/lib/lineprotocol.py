# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

import asyncio
import logging

LOGGER = logging.getLogger(__name__)


class LineProtocol(asyncio.Protocol):
    def __init__(self, callback):
        self._buffer = bytearray()
        self.callback = callback

    def data_received(self, data):
        self._buffer.extend(data)
        for line in self._lines():
            self.callback(line)

    def _lines(self):
        s_ind, e_ind = 0, -1 
        while e_ind != 0:
            e_ind = self._buffer.find(b'\n', s_ind) + 1
            if e_ind:
                line = self._buffer[s_ind:e_ind].decode('utf-8')
                yield line
                s_ind = e_ind
        if s_ind > 0:
            del self._buffer[:s_ind]


