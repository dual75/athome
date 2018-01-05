# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

import asyncio
import logging
import json
import collections

Line = collections.namedtuple('Line', ('req_id', 'message', 'payload'))

LINE_EXITED = 'exit'
LINE_START = 'start'
LINE_STARTED = 'started'
LINE_ERROR = 'error'

TEXT_ENCODING = 'utf-8'

NEW_LINE = 10

LOGGER = logging.getLogger(__name__)


def encode_line(line):
    message = {
        'req_id': line.req_id,
        'message': line.message,
        'payload': line.payload
    }
    return (json.dumps(message) + '\n').encode(TEXT_ENCODING)


def decode_line(text_line):
    message = json.loads(text_line.decode(TEXT_ENCODING))
    return Line(message['req_id'], message['message'], message['payload'])


class LineProtocol(asyncio.SubprocessProtocol):
    def __init__(self, line_callback, exit_callback = None):
        self._buffer = bytearray()
        self._line_callback = line_callback
        self._exit_callback = exit_callback

    def data_received(self, data):
        self._buffer.extend(data)
        for line in self._lines():
            self._line_callback(line)
    
    def pipe_data_received(self, fd, data):
        return self.data_received(data)

    def _lines(self):
        s_ind, e_ind = 0, -1 
        while e_ind != 0:
            e_ind = self._buffer.find(b'\n', s_ind) + 1
            if e_ind:
                line_bytes = self._buffer[s_ind:e_ind]
                if len(line_bytes) > 1:
                    # emtpy lines are not yielded
                    yield decode_line(line_bytes)
                s_ind = e_ind
        if s_ind > 0:
            del self._buffer[:s_ind]
    
    def connection_lost(self, exc):
        self._line_callback(None)

    def pipe_connection_lost(self, fd, exc):
        return self.connection_lost(exc)

    def process_exited(self):
        if self._exit_callback:
            self._exit_callback()
    
    def eof_received(self):
        if self._exit_callback:
            self._exit_callback()
