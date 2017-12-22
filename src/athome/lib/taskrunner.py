# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

import os
import sys
import importlib
import logging
import asyncio
import concurrent
import inspect
from functools import partial

from athome.api.task import Task
from athome.lib.runnersupport import RunnerSupport, runner_main

MODULE_PREFIX = '__athome_tasksmodule_'
TASK_PREFIX = 'task_'

LOGGER = logging.getLogger(__name__)


class TaskRunner(RunnerSupport):

    def __init__(self):
        super().__init__()
        self.plugins = dict()

    async def run_coro(self):
        while self.running:
            await self._directory_scan()
            await asyncio.sleep(self.config['poll_interval'])

    async def _directory_scan(self):
        """Scan plugins directory for new, deleted or modified files"""

        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            LOGGER.debug('tasks module check')
            all_files = await loop.run_in_executor(executor, partial(self._find_all, self.config['tasks_dir']))
            all_file_names = {f[0] for f in all_files}
            memory_file_names = set(self.plugins.keys())
            for fname in memory_file_names - all_file_names:
                await self._deactivate_task_module(fname)

            changed_files = self._find_changed(all_files)
            for fname, fpath, mtime in changed_files:
                if fname in list(self.plugins.keys()):
                    self._deactivate_task_module(fname)
                task_ = self._load_task_module(fname, fpath, mtime)
                self._activate_task(task_)

    def _activate_task(self, task_):
        """Add a plugin from current running set and start it

        :param plugin: plugin to be added

        """

        self.plugins[task_.name] = task_
        task_.start(self.loop)

    def _deactivate_task_module(self, name):
        """Remove a plugin from current

        :param name: name of the plugin to be removed

        """

        LOGGER.info('Stopping plugin %s', name)
        plugin_ = self.plugins[name]
        plugin_.stop()
        del self.plugins[name]

    @staticmethod
    def _find_all(plugins_dir):
        """Find all python modules in plugins dir"""

        result = [(f, os.path.join(plugins_dir, f))
                  for f in os.listdir(plugins_dir)
                  if f.endswith('.py')
                  and os.path.isfile(os.path.join(plugins_dir, f))
                  and os.access(os.path.join(plugins_dir, f), os.R_OK)
                  ]
        return result

    def _find_changed(self, files):
        """Find changed python modules in plugins dir

        Only files with mtime > plugin.mtime are to be considered
        changed.

        """

        result = []
        module_stamps = {
            plugin.name: plugin.mtime
            for plugin in self.plugins.values()
        }
        for fname, fpath in files:
            fstat = os.stat(fpath)
            if module_stamps.get(fname, 0) < fstat.st_mtime:
                result.append((fname, fpath, fstat.st_mtime))
        LOGGER.info("changed tasks modules: %s", str(result))
        return result

    @staticmethod
    def _import_module(module_name, fpath):
        """Import a module from source

        :param module_name: name of the module
        :param fpath: full path of the module source file

        """

        spec = importlib.util.spec_from_file_location(module_name, fpath)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def _load_task_module(self, fname, fpath, mtime):
        """Load a module from plugin directory

        :param fname: basename of the module file
        :param fpath: full path of the module file
        :param loop: asyncio loop

        """

        result = None
        module_name = MODULE_PREFIX + fname[:-3]
        module = self._import_module(module_name, fpath)
        coroutines = inspect.getmembers(module, inspect.iscoroutinefunction)
        task_coros = [c for c in coroutines if c[0].startswith(TASK_PREFIX)]
        loop = asyncio.get_event_loop()
        if task_coros:
            LOGGER.debug("found task %s", fname)
            result = Task(loop, fname, module, mtime,
                          dict(task_coros), self.tasks)
            sys.modules[module_name] = result
        else:
            LOGGER.warning(
                "%s not a plugin, missing coroutine 'engage'", fname)
            raise Exception('not a plugin module, missing coroutine "engage"')
        return result


if __name__ == '__main__':
    runner = TaskRunner()
    runner_main(runner, True)
