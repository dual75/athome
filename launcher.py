# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

"""
"""

import argparse
import asyncio
import logging
import logging.config
import logging.handlers
import os
import signal
import sys
from functools import partial

import yaml

from athome.core import Core

DEFAULT_CONFIG = './config.yml'
LOGGER = logging.getLogger(__name__)


if sys.platform == 'win32':
    loop = asyncio.ProactorEventLoop()
    asyncio.set_event_loop(loop)
LOOP = asyncio.get_event_loop()
CORE = Core()


def init_env(config_file):
    """Initialize logging an sys.path"""

    if not os.path.exists(config_file):
        raise FileNotFoundError("Configuration file {} not found".
                                    format(config_file))
    if os.path.isdir(config_file):
        raise IsADirectoryError("{} is not a file".format(config_file))
    config = yaml.safe_load(open(config_file, 'rb'))
    logconf = config['logging']
    logging.config.dictConfig(logconf)
    return config


def ask_exit(signame):
    """Handle interruptions via posix signals

    Parameters:
    signame: name of the signal
    """

    LOGGER.info("got signal %s exit", signame)
    CORE.stop()


def install_signal_handlers():
    """Install signal handlers for SIGINT and SIGTERM

    """

    signames = ('SIGINT', 'SIGTERM')
    if sys.platform != 'win32':
        for signame in signames:
            LOOP.add_signal_handler(getattr(signal, signame),
                                    partial(ask_exit, signame))


def main():
    parser = argparse.ArgumentParser(
        description='Manage @home server', prog='engine')
    parser.add_argument('-d', '--detach', action='store_true',
                        help='Run in background')
    parser.add_argument('-c', '--config', action='store_true',
                        help='Specify configuration file',
                        default=DEFAULT_CONFIG)
    parser.add_argument('-v', '--verbosity',
                        action='store_true', help='Turn on verbosity')
    args = parser.parse_args()
    config = init_env(args.config)
    LOOP.set_debug(config['asyncio']['debug'])
    if args.detach:
        pid = os.fork()
        if pid == -1:
            LOGGER.error('fork error')
            sys.exit(-1)
        elif pid != 0:
            sys.exit(0)
        else:
            os.setsid()
            os.umask(0)

    install_signal_handlers()
    try:
        CORE.initialize(LOOP, config)
        CORE.run_forever()
        result = 0
    except KeyboardInterrupt as ex:
        CORE.stop()
        LOGGER.info("Caught CTRL-C")
        result = 0
    except Exception as ex:
        LOGGER.exception(ex)
        result = -1
    CORE.shutdown()

    sys.exit(result)

    
if __name__ == '__main__':
    main()

