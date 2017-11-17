# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

"""
"""

import os
import sys
import signal
import asyncio
import logging

import yaml

import athome

LOGGER = logging.getLogger(__name__)

CORE = athome.Core()
LOOP = asyncio.get_event_loop()

def init_env():
    """Initialize logging an sys.path"""

    logging.basicConfig(level=logging.DEBUG)
    logging.getLogger('asyncio.poll').setLevel(logging.WARNING)
    logging.getLogger('hbmqtt').setLevel(logging.WARNING)
    logging.getLogger('transitions').setLevel(logging.WARNING)
    LOGGER.debug(sys.path)
    return yaml.load(open('config.yml', 'rb'))

def ask_exit():
    """Handle interruptions via posix signals
    
    Parameters:
    signame: name of the signal
    """

    LOGGER.info("got signal  exit")
    CORE.stop()

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
    config = init_env()
    LOOP.set_debug(True)
    #install_signal_handlers(LOOP, CORE)
    try:
        CORE.initialize(config)
        CORE.run_forever(LOOP)
        result = 0
    except KeyboardInterrupt as ex:
        LOGGER.info("Caught CTRL-C")
        result = 0
    except Exception as ex:
        LOGGER.exception(ex)
        result = -1
    finally:
        CORE.shutdown()
    sys.exit(result)


if __name__ == '__main__':
    main()
 
