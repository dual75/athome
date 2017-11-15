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

def init_env():
    """Initialize logging an sys.path"""

    logging.basicConfig(level=logging.DEBUG)
    logging.getLogger('hbmqtt').setLevel(logging.INFO)
    logging.getLogger('transitions').setLevel(logging.WARN)
    LOGGER.debug(sys.path)
    return yaml.load(open('config.yml', 'rb'))

async def ask_exit(signame):
    """Handle interruptions via posix signals
    
    Parameters:
    signame: name of the signal
    """

    LOGGER.info("got signal %s: exit" % signame)
    core.stop()


def install_signal_handlers(loop):
    """Install signal handlers for SIGINT and SIGTERM
    
    Parameters:
    param:
    """

    signames = ('SIGINT', 'SIGTERM')
    if os.name != 'nt':
        for signame in signames:
            loop.add_signal_handler(getattr(signal, signame),
                functools.partial(ask_exit, signame))

def main():
    config = init_env()
    loop = asyncio.get_event_loop()
    loop.set_debug(True)
    install_signal_handlers(loop)
    core = athome.Core()
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
 
