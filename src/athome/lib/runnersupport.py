# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

import asyncio
import json
import logging
import os
import signal
import sys
from functools import partial

import athome
from athome import MESSAGE_LINE, MESSAGE_SHUTDOWN, Message
from athome.lib.jobs import Executor
from athome.lib.lineprotocol import (LINE_START, LINE_STARTED,
                                     Line, LineProtocol, decode_line,
                                     encode_line)

LOGGER = logging.getLogger(__name__)


class LineLoggingHandler(logging.Handler):

    def __init__(self, stream):
        super().__init__()
        self._stream = stream
    
    def emit(self, record):
         self._stream.write(encode_line(Line(None, 'log', record))


class RunnerSupport:

    def __init__(self, name, loop=None):
        assert name is not None
        self.name = name
        self.loop = loop or asyncio.get_event_loop()
        self.messages = asyncio.Queue() 
        self.pipe_stream = None
        self.line_protocol = None
        self.env = None
        self.config = None
        self.executor = Executor(loop=self.loop)
        self.running = False
        for signame in 'SIGINT', 'SIGTERM':
            self.loop.add_signal_handler(
                getattr(signal, signame), 
                partial(self._handle_stop_signal, signame)
                )
        
    def pipe_in(self, line):
        self.messages.put_nowait(Message(MESSAGE_LINE, line, None))

    def sendline(self, message, payload=None, req_id=None):
        self.pipe_stream.write(encode_line(Line(req_id, message, payload)))

    async def run(self):
        _, self.line_protocol = await self.loop.connect_read_pipe(
            lambda: LineProtocol(self.pipe_in), 
            sys.stdin
        )
        self.pipe_stream, _ = await self.loop.connect_write_pipe(
            asyncio.BaseProtocol,
            sys.stdout
        )
        self.running = True
        await self._event_loop()

    async def run_coro(self):
        raise NotImplementedError

    async def term_coro(self):
        pass

    def _error_callback(self, exc):
        self.outcome = LINE_ERROR
        self.running = False
        self.messages.put_nowait(Message(MESSAGE_SHUTDOWN, None))
        
    async def _event_loop(self):
        try:
            while self.running or not self.messages.empty():
                msg = await self.messages.get()           
                if msg.type == MESSAGE_LINE:
                    LOGGER.debug('got line %s', msg.value)
                    line = msg.value
                    if line is None:
                        self.running = False
                    elif line.req_id:
                        await self._handle_request(line)
                    else:   
                        await self._handle_message(line)
            await self.executor.wait()
        except:
            LOGGER.exception('Error in event loop')
            raise

    async def _handle_request(self, line):
        handler = getattr(self, '{}_request_handler'.format(line.message), None)
        response_payload = {'error': None, 'error_tb': None, 'error_message': None,'payload': None}
        try:
            assert asyncio.iscoroutinefunction(handler)
            handler_result = await handler(line.payload)
            response_payload['response'] = handler_result
        except Exception as ex:
            tb = traceback.extract_tb(ex.__traceback__)
            response_payload['error'] = str(ex)
            response_payload['error_tb'] = traceback.format_list(tb)
            response_payload['error_message'] = str(ex)
        self.sendline('response', req_id=line.req_id, payload=response_payload)

    async def _handle_message(self, line):
        handler_name = '{}_message_handler'.format(line.message)
        assert hasattr(self, handler_name)
        handler = getattr(self, handler_name)
        assert asyncio.iscoroutinefunction(handler)
        LOGGER.debug('invoking line handler %s', handler)
        await handler(line.payload)

    async def start_message_handler(self, payload):
        self.env = payload['env']
        self.config = payload['subsystem_config']
        self.executor.execute(self.run_coro())
        self.sendline(LINE_STARTED)

    def _handle_stop_signal(self, signame):
        self.running = False


def runner_main(runner, logfile, debug=False):
    logging.basicConfig(level=debug and logging.DEBUG or logging.INFO, 
        handlers=[LineLoggingHandler(runner.pipe_stream)])
    os.setpgid(os.getpid(), os.getpid())

    loop = asyncio.get_event_loop()
    loop.set_debug(debug)
    task = asyncio.ensure_future(runner.run())
    try:
        loop.run_until_complete(task)
        loop.close()
    except:
        LOGGER.exception('Error in runner')
        sys.exit(athome.PROCESS_OUTCOME_KO)
    sys.exit(athome.PROCESS_OUTCOME_KO)
