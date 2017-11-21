# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

"""
"""

import argparse
import asyncio
import logging
import os
import signal
import sys
import yaml

from functools import partial

from athome.core import Core

DEFAULT_CONFIG = './config.yml'
LOGGER = logging.getLogger(__name__)

CORE = Core()
LOOP = asyncio.get_event_loop()


def init_env(config_file):
    """Initialize logging an sys.path"""

    config = yaml.load(open(config_file, 'rb'))
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
        CORE.initialize(config)
        CORE.run_forever(LOOP)
        result = 0
    except KeyboardInterrupt as ex:
        CORE.stop()
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
