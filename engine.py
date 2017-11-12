
# Copyright (c) 2017 Alessandro Duca
#
# See the file license.txt for copying permission.

import os, sys
import signal
import asyncio
import functools
import logging

import yaml

import athome

LOGGER = logging.getLogger(__name__)

config = yaml.load(open('config.yml', 'rb'))

def init_env():
    """Initialize logging an sys.path"""

    logging.basicConfig(level=logging.DEBUG)
    logging.getLogger('hbmqtt').setLevel(logging.INFO)
    logging.getLogger('transitions').setLevel(logging.WARN)
    LOGGER.debug(sys.path)

def ask_exit(signame):
    """Handle interruptions via posix signals"""

    LOGGER.info("got signal %s: exit" % signame)
    athome.core.stop_running()

def activate_main_tasks(loop):
    """Create main asyncio tasks

    Parameters
    ----------
    loop: asyncio loop
    """

    LOGGER.info("in activate_main_tasks(loop)")
    result = asyncio.gather(
        athome.mqtt.start_broker(config['subsystem']['hbmqtt']),
        athome.plugins.watch_plugin_dir(config['subsytem']['plugins'], loop)
    )
    return result

def install_signal_handlers(loop):
    """Install signal handlers for SIGINT and SIGTERM"""

    for signame in ('SIGINT', 'SIGTERM'):
        loop.add_signal_handler(getattr(signal, signame),
            functools.partial(ask_exit, signame))

def main():
    init_env()
    try:
        loop = athome.core.startup(config)
        install_signal_handlers(loop)
        athome.core.run_until_complete()
        result = 0
    except Exception as ex:
        LOGGER.exception(ex)
        result = -1
    finally:
        athome.core.shutdown()
    sys.exit(result)

 
if __name__ == '__main__':
    main()
 
