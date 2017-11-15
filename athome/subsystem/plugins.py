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

from transitions import Machine

import athome

ENGAGE_METHOD   = 'engage'
SHUTDOWN_METHOD = 'shutdown'
MODULE_PREFIX   = '__athome_'

LOGGER = logging.getLogger(__name__)

_plugins = dict()


class Plugin(object):

    states = [
        'ready',
        'running',
        'closed'
    ]

    transitions = [
            {
                'trigger':'start',
                'source':'ready',
                'dest':'running',
                'before': ['_on_start']
                },
            {
                'trigger':'stop',
                'source':'running',
                'dest':'ready',
                'before': ['_on_stop']
                },
            {
                'trigger':'close',
                'source': ['loaded', 'ready', 'running'],
                'dest':'ready',
                'before': ['_on_close']
                }
    ]

    def __init__(self, loop, name, module, mtime):
        self.machine = Machine(model=self,
                            states=Plugin.states,
                            transitions=Plugin.transitions,
                            initial='ready')
        self.name = name
        self.module = module
        self.mtime = mtime
        self.loop = loop
        self._task_coro = None

    async def _wrap_coro(self):
        with contextlib.suppress(concurrent.futures.CancelledError):
            try:
                await getattr(self.module, ENGAGE_METHOD)(self.loop)
            except Exception as ex:
                LOGGER.exception('Exception occurred in plugin {}'.format(self.name), ex)
                
    def _on_start(self, loop):
        """Create a new task for plugin"""

        self._task_coro = asyncio.ensure_future(self._wrap_coro(), loop=self.loop)
        shutdown = getattr(self.module, SHUTDOWN_METHOD, None)
        callback = None
        if shutdown:
            def callback_func(future):
                shutdown()
            callback = callback_func
        else:
            def callback_func(future):
                pass
            callback = callback_func
        self._task_coro.add_done_callback(callback)

    def _on_stop(self):
        if not self._task_coro.done():
            self._task_coro.cancel()
        self._task_coro = None

    def _on_close(self):
        if self.state == 'running':
            self._on_stop()


class Subsystem(athome.core.SystemModule):

    def __init__(self, name):
        super().__init__(name)
        self.running = None

    def on_start(self, loop):
        """None"""

        super().on_start(loop)
        self.running = True

    def on_stop(self):
        self.running = False

    async def run(self):       
        try:
            while self.running:
                await self._directory_scan()
                await asyncio.sleep(self.config['plugin_poll_interval'])
            LOGGER.debug('Exited watch cycle')
        except Exception as ex:
            LOGGER.exception('Error in watch_plugin_dir cycle', ex)

    async def _directory_scan(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            all_files = await self.loop.run_in_executor(executor,
                                                   partial(
                                                     self._find_all,
                                                     self.config['plugins_dir']
                                                     )
                                                   )
            all_file_names = {f[0] for f in all_files}
            memory_file_names = set(_plugins.keys())
            for fname in memory_file_names - all_file_names:
                await self._remove_plugin(fname)

            changed_files = self._find_changed(all_files)
            for fname, fpath, mtime in changed_files:
                if fname in _plugins:
                    await self._remove_plugin(fname)
                plugin = self._load_plugin_module(fname, fpath, self.loop, mtime)
                self._register_plugin(plugin)


    def _register_plugin(self, plugin):
        _plugins[plugin.name] = plugin
        plugin.start(self.loop)


    async def _remove_plugin(self, name):
        plugin = _plugins[name]
        plugin.stop()
        del _plugins[name]


    def _find_all(self, plugins_dir):
        result = [(f, os.path.join(plugins_dir, f))
                for f in os.listdir(plugins_dir)
                if f.endswith('.py')
                and os.path.isfile(os.path.join(plugins_dir, f))
            ]
        LOGGER.info("existing plugin modules: {}".format(str(result)))
        return result

        
    def _find_changed(self, files):
        result = []
        module_stamps = {
            plugin.name: plugin.mtime
            for plugin in _plugins.values()
            }
        for fname, fpath in files:
            fstat = os.stat(fpath)
            if module_stamps.get(fname, 0) < fstat.st_mtime:
                result.append((fname, fpath, fstat.st_mtime))
        LOGGER.info("changed plugin modules: {}".format(str(result)))
        return result
        

    def _import_module(self, module_name, fpath):
        spec = importlib.util.spec_from_file_location(module_name, fpath)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


    def _load_plugin_module(self, fname, fpath, loop, mtime):
        result = None
        module_name = MODULE_PREFIX + fname[:-3]
        module = self._import_module(module_name, fpath)
        engage = getattr(module, ENGAGE_METHOD, None)
        if engage and asyncio.iscoroutinefunction(engage):
            LOGGER.debug("found plugin {}".format(fname))
            result = Plugin(loop, fname, module, mtime)
            sys.modules[module_name] = result
        else:
            LOGGER.warn("%s not a plugin, missing coroutine 'engage'" % fname)
            raise Exception('not a plugin module, missing coroutine "engage"')
        return result

