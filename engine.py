# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

"""
"""

import os, sys
import signal
import asyncio
import functools
import logging

import yaml

import athome

LOGGER = logging.getLogger(__name__)

core = None
loop = None

def init_env():
    """Initialize logging an sys.path"""

    logging.basicConfig(level=logging.DEBUG)
    logging.getLogger('hbmqtt').setLevel(logging.INFO)
    logging.getLogger('transitions').setLevel(logging.WARN)
    LOGGER.debug(sys.path)
    return yaml.load(open('config.yml', 'rb'))

def ask_exit():
    """Handle interruptions via posix signals
    
    Parameters:
    signame: name of the signal
    """

    LOGGER.info("got signal  exit")
    core.stop()

def install_signal_handlers(loop, core):
    """Install signal handlers for SIGINT and SIGTERM
    
    Parameters:
    param:
    """

    signames = ('SIGINT', 'SIGTERM')
    if os.name != 'nt':
        for signame in signames:
            loop.add_signal_handler(getattr(signal, signame), ask_exit)

def main():
    global loop, core

    config = init_env()
    loop = asyncio.get_event_loop()
    loop.set_debug(True)
    core = athome.Core()
    install_signal_handlers(loop, core)
    try:
        core.initialize(config)
        core.run_until_complete(loop)
        result = 0
    except KeyboardInterrupt as ex:
        LOGGER.info("Caught CTRL-C")
        result = 0
    except Exception as ex:
        LOGGER.exception(ex)
        result = -1
    finally:
        core.shutdown()
    sys.exit(result)

if __name__ == '__main__':
    main()
 
