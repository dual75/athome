# Copyright (c) 2017,2011 Alessandro Duca <alessandro.duca@gmail.com>
# All rights reserved.
# 
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
# 
# 1. Redistributions of source code must retain the above copyright notice,
#   this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#   notice, this list of conditions and the following disclaimer in the
#   documentation and/or other materials provided with the distribution.
# 3. Neither the name of mosquitto nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

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


class PluginManager(object):

    __instance = None

    plugins = {}

    def __new__(cls):
        if PluginManager.__instance is None:
            PluginManager.__instance = object.__new__(cls)
        return PluginManager.__instance

    async def watch_plugin_dir(self, config, loop):
        with concurrent.futures.ProcessPoolExecutor(max_workers=1) as executor:
            while loop.is_running():
                all_files = await loop.run_in_executor(executor,
                                                       partial(
                                                           self._find_all,
                                                           config['plugins_dir']
                                                           )
                                                       )

                all_file_names = {f[0] for f in all_files}
                memory_file_names = set(self.plugins.keys())
                for fname in memory_file_names - all_file_names:
                    self.remove_plugin(fname)

                changed_files = self._find_changed(all_files)
                for fname, fpath, mtime in changed_files:
                    if fname in self.plugins:
                        self.remove_plugin(fname)
                    plugin = load_plugin_module(fname, fpath, loop, mtime)
                    self.register_plugin(plugin)
                    
                await asyncio.sleep(config['reload_interval'])

    def register_plugin(self, plugin):
        self.plugins[plugin.name] = plugin
        plugin.start()

    def remove_plugin(self, name):
        plugin = self.plugins[name]
        plugin.stop()
        del self.plugins[name]

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
            for plugin in self.plugins.values()
            }
        for fname, fpath in files:
            fstat = os.stat(fpath)
            if module_stamps.get(fname, 0) < fstat.st_mtime:
                result.append((fname, fpath, fstat.st_mtime))
            LOGGER.info("changed plugin modules: {}".format(str(result)))
        return result
        

def import_module(module_name, fpath):
    spec = importlib.util.spec_from_file_location(module_name, fpath)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_plugin_module(fname, fpath, loop, mtime):
    result = None
    module_name = MODULE_PREFIX + fname[:-3]
    module = import_module(module_name, fpath)
    engage = getattr(module, ENGAGE_METHOD, None)
    if engage and asyncio.iscoroutinefunction(engage):
        LOGGER.debug("found plugin {}".format(fname))
        result = Plugin(loop, fname, module, mtime)
        sys.modules[module_name] = result
    else:
        LOGGER.warn("%s not a plugin, missing coroutine 'engage'" % fname)
    return result
    


watch_plugin_dir = PluginManager().watch_plugin_dir
    

