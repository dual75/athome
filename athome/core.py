import asyncio
import logging
import importlib

LOGGER = logging.getLogger(__name__)

_loop = None
_subsystems = {}

config = None


class Subsystem:
    STARTUP_CORO = 'startup'
    SHUTDOWN_CORO = 'shutdown'

    def __init__(self, name, module):
        self.name = name
        self.module = module
        self.run_task = None
        self.in_queue = asyncio.Queue()
        self._shutdown_task = None

    def startup(self, config):
        startup_coro = getattr(self.module, self.STARTUP_CORO)
        self.run_task = _loop.create_task(startup_coro(_loop, 
                                                        config,
                                                        self.in_queue) 
                                            )
        LOGGER.debug('Subsystem {} started'.format(self.name))

    def shutdown(self):
        shutdown_coro = getattr(self.module, self.SHUTDOWN_CORO, None)
        try:
            LOGGER.debug('Now awaiting shutdown_task for subsystem %s' % 
                         self.module.__name__)
            _loop.run_until_complete(shutdown_coro())
        except Exception as e:
            LOGGER.exception(e)
            
        if not self.run_task.done():
            self.run_task.cancel()
        try:
            LOGGER.debug('Now awaiting _module_coro %s' % self.module.__name__)
            _loop.run_until_complete(self.run_task)
        except Exception as e:
            LOGGER.exception(e)


def startup(config_):
    global _loop, config
    _loop = asyncio.get_event_loop()
    config = config_

    for name in [name for name in config['subsystem'] 
                        if config['subsystem'][name]['enable']
                        ]:
        LOGGER.debug('Loading module {}'.format(name))
        module_name = 'athome.subsystem.{}'.format(name)
        module = importlib.import_module(module_name)
        subsystem = _subsystems[name] = Subsystem(name, module)
        LOGGER.info('Starting subsystem %s' % name)
        subsystem.startup(config['subsystem'][name]['config'])
    return _loop


def run_until_complete():
    tasks = [subsystem.run_task for subsystem in _subsystems.values()]
    task = asyncio.gather(*tasks)
    _loop.run_until_complete(task)


def stop_running():
    for subsystem in _subsystems.values():
        subsystem.in_queue.put_nowait('stop')


def shutdown():
    global _loop, config
    for subsystem in _subsystems.values():
        shutdown_task = _loop.create_task(subsystem.shutdown())
        try:
            _loop.run_until_complete(shutdown_task)
        except Exception as e:
            LOGGER.error('Error while shutting down subsystem {}'.format(subsystem.name))
            LOGGER.exception(e)
    if _loop:
        _loop.stop()
        _loop.close()
    _loop = config = None

        
