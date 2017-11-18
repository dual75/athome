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

from functools import partial

import yaml

import athome

LOGGER = logging.getLogger(__name__)

CORE = athome.Core()
LOOP = asyncio.get_event_loop()

def init_env():
    """Initialize logging an sys.path"""

    config = yaml.load(open('config.yml', 'rb')) 
    logconf = config['logging']
    logging.basicConfig(**logconf['basicConfig'])
    for pkg in logconf['packages']:
        logging.getLogger(pkg).setLevel(getattr(
                                               logging, 
                                               logconf['packages'][pkg]
                                               )
                                       )
    LOGGER.debug(sys.path)
    return config

def ask_exit(signame):
    """Handle interruptions via posix signals
    
    Parameters:
    signame: name of the signal
    """

    LOGGER.info("got signal %s exit" % signame)
    CORE.stop()

def install_signal_handlers():
    """Install signal handlers for SIGINT and SIGTERM
    
    Parameters:
    param:
    """

    signames = ('SIGINT', 'SIGTERM')
    if os.name != 'nt':
        for signame in signames:
            LOOP.add_signal_handler(getattr(signal, signame), 
                            partial(ask_exit, signame))

def main():
    config = init_env()
    LOOP.set_debug(config['asyncio']['debug'])
    install_signal_handlers()
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
 
