# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.
import unittest
import asyncio

from functools import partial

class AsyncTest(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()

    def complete(self, *tasks):
        single = asyncio.gather(*tasks)
        self.loop.run_until_complete(single)


class SubsystemTest(AsyncTest):
    pass
    
