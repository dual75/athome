import asyncio
import logging
import importlib
from functools import partial

LOGGER = logging.getLogger(__name__)

from transitions import Machine

class SystemModule():

    states = [
                'loaded',
                'ready',
                'running',
                'closed',
                'failure'
              ]

    transitions = [
            {
                'trigger':'initialize',
                'source':'loaded',
                'dest':'ready',
                'before': ['on_initialize']
                },
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
                'trigger':'shutdown',
                'source':['loaded', 'ready', 'running'],
                'dest':'closed',
                'before': ['_on_shutdown']
                }
        ]

    def __init__(self, loop, name):
        self.name = name
        self.machine = Machine(model=self,
                            states=SystemModule.states,
                            transitions=SystemModule.transitions,
                            initial='loaded')
        self.loop = loop
        self.config = None
        self.run_task = None
        self.in_queue, self.out_queue = asyncio.Queue(), asyncio.Queue()

    def on_initialize(self, config):
        self.config = config

    async def run(self):
        LOGGER.debug("run does nothing by default")

    def on_start(self):
        raise NotImplementedError

    def on_stop(self):
        raise NotImplementedError

    def on_shutdown(self):
        LOGGER.debug("on_shutdown does nothing by default")

    def _on_start(self):
        if self.state is not 'ready':
            raise Exception('Subsystem not in "running" state')

        async def start_coro():
            self.on_start()
            await self.run()

        self.run_task = asyncio.ensure_future(start_coro(), loop=self.loop)

    def _on_stop(self):
        self.on_stop()
        asyncio.wait(self.run_task, loop=self.loop)
        self.run_task = None

    def _on_shutdown(self):
        LOGGER.debug('Now awaiting shutdown_task for %s' % self.name)
        try:
            if self.state == 'running':
                self.on_stop()
            self.on_shutdown()
        except Exception as ex:
            LOGGER.exception("Subsystem %s shutdown in error" % subsystem.name, ex)

        if self.run_task and not self.run_task.done():
            LOGGER.info("Now canceling run_task for subsystem")
            try:
                asyncio.wait_for(self.run_task, timeout=2.0, loop=self.loop)
            except asyncio.TimeoutError as ex:
                LOGGER.exception("Subsystem %s run_task canceled" % subsystem.name)
        

class Core(SystemModule):

    __instance = None

    def __new__(cls):
        if Core.__instance is None:
            Core.__instance = object.__new__(cls)
            Core.__instance.__initialized = False
        return Core.__instance

    def __init__(self):
        if not self.__initialized:
            loop = asyncio.get_event_loop()
            super().__init__(loop, 'core')
            self.subsystems = {}
            self.__initialized = True
    
    def on_initialize(self, config):
        super().on_initialize(config)

        # Load subsystems
        for name in [name for name in config['subsystem'] 
                            if config['subsystem'][name]['enable']
                            ]:
            LOGGER.debug('Loading module {}'.format(name))
            module_name = 'athome.subsystem.{}'.format(name)
            module = importlib.import_module(module_name)
            subsystem_class = getattr(module, 'Subsystem')
            subsystem = self.subsystems[name] = subsystem_class(self.loop, name)
            LOGGER.info('Starting subsystem %s' % name)
            subsystem.initialize(config['subsystem'][name]['config'])

    def on_start(self):
        for subsystem in self.subsystems.values():
            subsystem.start()

    async def run(self):
        await asyncio.gather(*[
            subsystem.run_task
                for subsystem in self.subsystems.values()
            ])
        
    def on_stop(self):
        subsystems = self.subsystems.values()
        for subsystem in self.subsystems.values():
            subsystem.stop()

    def on_shutdown(self):
        for subsystem in self.subsystems.values():
            subsystem.shutdown()
        try:
            self.loop.stop()
        finally:
            self.loop.close()

    def run_until_complete(self):
        self.start()
        self.loop.run_until_complete(self.run_task)

        
