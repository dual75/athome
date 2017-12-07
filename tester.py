

import os 
import sys
import asyncio
import functools

from athome.subsystem import plugins
from athome.lib import pluginrunner

def main():
    if sys.platform == 'win32':
        loop = asyncio.ProactorEventLoop()
        asyncio.set_event_loop(loop)
    loop = asyncio.get_event_loop()
    q = asyncio.Queue()
    s = plugins.Subsystem('s', q)
    s.initialize(loop,
        {
            'plugindir':'plugins'
        }
    )
    task = asyncio.ensure_future(s.run())
    loop.run_until_complete(task)


if __name__ == '__main__':
    main()