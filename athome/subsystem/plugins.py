# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

import os
import sys
import asyncio
import logging
import concurrent
from  importlib import util
from functools import partial

from athome.module import SystemModule
from athome.api import plugin

MODULE_PREFIX = '__athome_'

LOGGER = logging.getLogger(__name__)


class Subsystem(SystemModule):
    """Plugins subsystem"""
    
    def __init__(self, name, await_queue):
        super().__init__(name, await_queue)
        self.running = True
        self.plugins = {}

    def on_stop(self):
        """'stop' event callback method"""

        for name in list(self.plugins.keys()):
            self._remove_plugin(name)
        self.running = False
        self.plugins = None

    async def run(self):      
        """Subsystem activity method

        This method is a *coroutine*.
        """ 

        while self.running:
            await self._directory_scan()
            await asyncio.sleep(self.config['plugin_poll_interval'])

    async def _directory_scan(self):
        """Scan plugins directory for new, deleted or modified files"""

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            all_files = await self.loop.run_in_executor(executor,
                                                        partial(
                                                            self._find_all,
                                                            self.config['plugins_dir']
                                                             )
                                                       )
            all_file_names = {f[0] for f in all_files}
            memory_file_names = set(self.plugins.keys())
            for fname in memory_file_names - all_file_names:
                await self._remove_plugin(fname)

            changed_files = self._find_changed(all_files)
            for fname, fpath, mtime in changed_files:
                if fname in list(self.plugins.keys()):
                    self._remove_plugin(fname)
                plugin_ = self._load_plugin_module(fname, fpath, self.loop, mtime)
                self._register_plugin(plugin_)

    def _register_plugin(self, plugin):
        """Add a plugin from current running set and start it

        :param plugin: plugin to be added

        """

        self.plugins[plugin.name] = plugin
        plugin.start(self.loop)

    def _remove_plugin(self, name):
        """Remove a plugin from current 

        :param name: name of the plugin to be removed 

        """

        LOGGER.info('Stopping plugin %s', name)
        plugin_ = self.plugins[name]
        plugin_.stop()
        del self.plugins[name]

    def _find_all(self, plugins_dir):
        result = [(f, os.path.join(plugins_dir, f))
                  for f in os.listdir(plugins_dir)
                  if f.endswith('.py')
                  and os.path.isfile(os.path.join(plugins_dir, f))
                 ]
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
        LOGGER.info("changed plugin modules: %s", str(result))
        return result  

    @staticmethod
    def _import_module(module_name, fpath):
        """Import a module from source

        :param module_name: name of the module
        :param fpath: full path of the module source file

        """

        spec = util.spec_from_file_location(module_name, fpath)
        module = util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def _load_plugin_module(self, fname, fpath, loop, mtime):
        """Load a module from plugin directory

        :param fname: basename of the module file
        :param fpath: full path of the module file
        :param loop: asyncio loop

        """

        result = None
        module_name = MODULE_PREFIX + fname[:-3]
        module = self._import_module(module_name, fpath)
        engage = getattr(module, plugin.ENGAGE_METHOD, None)
        if engage and asyncio.iscoroutinefunction(engage):
            LOGGER.debug("found plugin %s", fname)
            result = plugin.Plugin(loop, fname, module, mtime, self.await_queue)
            sys.modules[module_name] = result
        else:
            LOGGER.warning("%s not a plugin, missing coroutine 'engage'", fname)
            raise Exception('not a plugin module, missing coroutine "engage"')
        return result

