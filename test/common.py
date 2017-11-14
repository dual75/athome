# Copyright (c) 2017 Alessandro Duca
#
# See the file license.txt for copying permission.
import unittest
import asyncio

from functools import partial

class AsyncTest(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.get_event_loop()


class SubsystemTest(AsyncTest):
    pass
    
