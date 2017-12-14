# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

import os
import sys
import json
import importlib
import logging
import asyncio
import concurrent
from functools import partial

from athome import Message, MESSAGE_LINE
from athome.api import plugin
from athome.lib.lineprotocol import LineProtocol

MODULE_PREFIX = '__athome_plugin_'

LOGGER = logging.getLogger(__name__)


class Runner:

    def __init__(self, plugins_dir, check_interval):
        self.events = asyncio.Queue()
        self.pipe_stream = None
        self.plugins = dict()
        self.plugins_dir = plugins_dir
        self.check_interval = check_interval
        self.run_task = None
        
    def pipe_in(self, line):
        LOGGER.info('protocol yieled line: %s', line)
        self.events.put_nowait(Message(MESSAGE_LINE, line[:-1]))
        self.pipe_out(line)

    def pipe_out(self, str_):
        self.pipe_stream.write((str_ + '\n').encode('utf-8'))

    async def run(self):
        loop = asyncio.get_event_loop()
        _, protocol = await loop.connect_read_pipe(
            lambda: LineProtocol(self.pipe_in), 
            sys.stdin
        )
        self.pipe_stream, _ = await loop.connect_write_pipe(
            asyncio.BaseProtocol,
            sys.stdout
        )
        self.running = True
        await asyncio.gather(
                asyncio.ensure_future(self._directory_scan_loop()),
                asyncio.ensure_future(self._event_loop())
                )
        
    async def _event_loop(self):
        while self.running or not self.events.empty():
            msg = await self.events.get()
            LOGGER.info('Runner got msg %s: %s', msg.type, msg.value)
            
            if msg.type == MESSAGE_LINE:
                LOGGER.debug('got event %s', msg.value)
                command, arg = self.parseLine(msg.value)
                if command == 'stop':
                    self.pipe_out('exit')
                    self.running = False
                elif command == 'config':
                    pass
            else:
                task = msg.value
                if not task.done():
                    task.cancel()
                try:
                    await task
                except asyncio.CancelledError as ex:
                    LOGGER.debug('Cancelled task %s', task)
                finally:
                    LOGGER.debug('awaited %s', task)

    def parseLine(self, line):
        command, arg, chunks = line, None, line.split(' ', 1)
        if len(chunks) > 1:
            command, args = chunks[0], chunks[1]
            arg = json.loads(args)
        return command, arg

    async def _directory_scan_loop(self):
        while self.running:
            await self._directory_scan()
            await asyncio.sleep(self.check_interval)

    def fire_and_forget(self, coro):
        """Create task from coro or awaitable and put it into await_queue"""

        task = asyncio.ensure_future(coro)
        self.events.put_nowait(Message(MESSAGE_NONE, task))

    # shortcut for function
    faf = fire_and_forget

    async def _directory_scan(self):
        """Scan plugins directory for new, deleted or modified files"""

        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            LOGGER.debug('plugin check')
            all_files = await loop.run_in_executor(executor,
                                                    partial(
                                                            self._find_all,
                                                            self.plugins_dir
                                                    )
                                                  )
            all_file_names = {f[0] for f in all_files}
            memory_file_names = set(self.plugins.keys())
            for fname in memory_file_names - all_file_names:
                await self._deactivate_plugin(fname)

            changed_files = self._find_changed(all_files)
            for fname, fpath, mtime in changed_files:
                if fname in list(self.plugins.keys()):
                    self._deactivate_plugin(fname)
                plugin_ = self._load_plugin_module(fname, fpath, mtime)
                self._activate_plugin(plugin_)


    def _activate_plugin(self, plugin_):
        """Add a plugin from current running set and start it

        :param plugin: plugin to be added

        """

        self.plugins[plugin_.name] = plugin_
        plugin_.start(asyncio.get_event_loop())

    def _deactivate_plugin(self, name):
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
        LOGGER.info("changed plugin modules: %s", str(result))
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

    def _load_plugin_module(self, fname, fpath, mtime):
        """Load a module from plugin directory

        :param fname: basename of the module file
        :param fpath: full path of the module file
        :param loop: asyncio loop

        """

        result = None
        module_name = MODULE_PREFIX + fname[:-3]
        module = self._import_module(module_name, fpath)
        engage = getattr(module, plugin.ENGAGE_METHOD, None)
        loop = asyncio.get_event_loop()
        if engage and asyncio.iscoroutinefunction(engage):
            LOGGER.debug("found plugin %s", fname)
            result = plugin.Plugin(loop, fname, module,
                                   mtime, self.events)
            sys.modules[module_name] = result
        else:
            LOGGER.warning(
                "%s not a plugin, missing coroutine 'engage'", fname)
            raise Exception('not a plugin module, missing coroutine "engage"')
        return result
             

def main():
    logging.basicConfig(level=logging.DEBUG)
    os.setpgid(os.getpid(), os.getpid())

    loop = asyncio.get_event_loop()
    loop.set_debug(True)
    runner = Runner(sys.argv[1], int(sys.argv[2]))
    task = asyncio.ensure_future(runner.run())
    loop.run_until_complete(task)

    tasks = asyncio.Task.all_tasks()
    if tasks:
        for task in tasks:
            task.cancel()
        gather_task = asyncio.gather(*tasks, 
            loop=loop, 
            return_exceptions=True
        )
        loop.run_until_complete(gather_task)

    loop.close()
    sys.exit(0)


if __name__ == '__main__':
    main()

