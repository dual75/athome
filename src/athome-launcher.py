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
import tempfile
from functools import partial

import yaml

import athome
from athome.core import Core

DEFAULT_CONFIG = './config.yml'
LOGGER = logging.getLogger(__name__)

WIN32 = sys.platform == 'win32'


def init_env(config_file):
    """Initialize logging an sys.path"""

    if not os.path.exists(config_file):
        raise FileNotFoundError("Configuration file {} not found".
                                    format(config_file))
    if os.path.isdir(config_file):
        raise IsADirectoryError("{} is not a file".format(config_file))

    if not os.access(config_file, os.R_OK):
        raise FileNotFoundError("Configuration file {} not accessible".
                                    format(config_file))
    config = yaml.safe_load(open(config_file, 'rb'))
    logconf = config['logging']
    logging.config.dictConfig(logconf)
    env = process_env(config['env'])
    return env, config


def process_env(core_config):
    if WIN32:
        result = init_files_windows(core_config)
    else:
        result = init_files_linux(core_config)
    return result


def init_files_windows(core_config):
    result = dict()
    for parm in 'tmp_dir', 'run_dir':
        if core_config[parm] == 'auto':
            result[parm] = tempfile.gettempdir()
        else:
            result[parm] = core_config[parm] 
        assert validate_writeable_dir(result[parm])
    return result


def init_files_linux(core_config):
    result = dict()
    for parm, default in ('tmp_dir', tempfile.gettempdir()), ('run_dir', os.getcwd()):
        if core_config[parm] == 'auto':
            result[parm] = default
        else:
            result[parm] = core_config[parm] 
        assert validate_writeable_dir(result[parm])
    return result
        

def validate_writeable_dir(dir_file):
    return os.path.isdir(dir_file) and os.access(dir_file, os.R_OK | os.W_OK)


def ask_exit(signame, core):
    """Handle interruptions via posix signals

    Parameters:
    signame: name of the signal
    """

    LOGGER.info("got signal %s exit", signame)
    core.shutdown()


def install_signal_handlers(core):
    """Install signal handlers for SIGINT and SIGTERM

    """

    signames = ('SIGINT', 'SIGTERM')
    if sys.platform != 'win32':
        for signame in signames:
            loop.add_signal_handler(getattr(signal, signame),
                                    partial(ask_exit, signame, core))


def parse_args():
    parser = argparse.ArgumentParser(
        description='Manage @home server', prog='engine')
    parser.add_argument('-d', '--detach', action='store_true',
                        help='Run in background')
    parser.add_argument('-c', '--config', action='store',
                        help='Specify configuration file',
                        default=DEFAULT_CONFIG)
    parser.add_argument('-v', '--verbosity',
                        action='store_true', help='Turn on verbosity')
    return parser.parse_args()


def do_fork():
    pid = os.fork()
    if pid == -1:
        LOGGER.error('fork error')
        sys.exit(-1)
    elif pid != 0:
        sys.exit(0)
    else:
        os.setsid()
        os.umask(0)


async def main(loop, env, config):
    core = Core()
    core.initialize(loop, env, config)
    install_signal_handlers(core)
    result = athome.PROCESS_OUTCOME_KO
    try:
        await core.run_forever()
        result = athome.PROCESS_OUTCOME_OK
    except KeyboardInterrupt as ex:
        LOGGER.info("Caught CTRL-C")
        result = athome.PROCESS_OUTCOME_OK
    except Exception as ex:
        LOGGER.exception(ex)
    return result

def cleanup_tasks(loop):
    tasks = asyncio.Task.all_tasks()
    single = asyncio.gather(*tasks, loop=loop)
    single.cancel()
    try:
        loop.run_until_complete(single)
    except asyncio.CancelledError:
        pass

if WIN32:
    loop = asyncio.ProactorEventLoop()
    asyncio.set_event_loop(loop)

args = parse_args()
env, config = init_env(args.config)
loop = asyncio.get_event_loop()
loop.set_debug(config['asyncio']['debug'])
main_task = asyncio.ensure_future(main(loop, env, config))
result = loop.run_until_complete(main_task)
cleanup_tasks(loop)
loop.close()

sys.exit(result)
