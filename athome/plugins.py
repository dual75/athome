# Copyright (c) 2017 Alessandro Duca
#
# See the file license.txt for copying permission.

import os, sys
import asyncio
import logging
import functools
import concurrent
import importlib
import contextlib
from functools import partial

ENGAGE_METHOD   = 'engage'
SHUTDOWN_METHOD = 'shutdown'
MODULE_PREFIX   = '__athome_'

LOGGER = logging.getLogger(__name__)

__plugins = dict()


class Plugin(object):
    def __init__(self, loop, name, module, mtime):
        self.name = name
        self.module = module
        self.mtime = mtime
        self.loop = loop
        self._task_coro = None

    async def _wrap_coro(self):
        with contextlib.suppress(concurrent.futures.CancelledError):
            await getattr(self.module, ENGAGE_METHOD)(self.loop)

    def start(self):
        self._task_coro = self.loop.create_task(self._wrap_coro())

    def stop(self):
        shutdown = getattr(self.module, SHUTDOWN_METHOD, None)
        if shutdown and asyncio.iscoroutinefunction(shutdown):
            shutdown_task = self.loop.create_task(shutdown())
            shutdown_task.add_done_callback(self._task_coro.cancel)
        if not self._task_coro.done():
            self._task_coro.cancel()

    def is_alive(self):
        pass


async def watch_plugin_dir(config, loop):
    with concurrent.futures.ProcessPoolExecutor(max_workers=1) as executor:
        while loop.is_running():
            all_files = await loop.run_in_executor(executor,
                                                   partial(
                                                       _find_all,
                                                       config['plugins_dir']
                                                       )
                                                   )

            all_file_names = {f[0] for f in all_files}
            memory_file_names = set(__plugins.keys())
            for fname in memory_file_names - all_file_names:
                remove_plugin(fname)

            changed_files = _find_changed(all_files)
            for fname, fpath, mtime in changed_files:
                if fname in __plugins:
                    _remove_plugin(fname)
                plugin = _load_plugin_module(fname, fpath, loop, mtime)
                _register_plugin(plugin)
                
            await asyncio.sleep(config['reload_interval'])


def _register_plugin(plugin):
    __plugins[plugin.name] = plugin
    plugin.start()


def _remove_plugin(name):
    plugin = __plugins[name]
    plugin.stop()
    del __plugins[name]


def _find_all(plugins_dir):
    result = [(f, os.path.join(plugins_dir, f))
            for f in os.listdir(plugins_dir)
            if f.endswith('.py')
            and os.path.isfile(os.path.join(plugins_dir, f))
        ]
    LOGGER.info("existing plugin modules: {}".format(str(result)))
    return result

    
def _find_changed(files):
    result = []
    module_stamps = {
        plugin.name: plugin.mtime
        for plugin in __plugins.values()
        }
    for fname, fpath in files:
        fstat = os.stat(fpath)
        if module_stamps.get(fname, 0) < fstat.st_mtime:
            result.append((fname, fpath, fstat.st_mtime))
    LOGGER.info("changed plugin modules: {}".format(str(result)))
    return result
    

def _import_module(module_name, fpath):
    spec = importlib.util.spec_from_file_location(module_name, fpath)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_plugin_module(fname, fpath, loop, mtime):
    result = None
    module_name = MODULE_PREFIX + fname[:-3]
    module = _import_module(module_name, fpath)
    engage = getattr(module, ENGAGE_METHOD, None)
    if engage and asyncio.iscoroutinefunction(engage):
        LOGGER.debug("found plugin {}".format(fname))
        result = Plugin(loop, fname, module, mtime)
        sys.modules[module_name] = result
    else:
        LOGGER.warn("%s not a plugin, missing coroutine 'engage'" % fname)
        raise Exception('not a plugin module, missing coroutine "engage"')
    return result

    

