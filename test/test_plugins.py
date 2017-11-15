# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

"""
"""

import os
import shutil
import unittest
import types
import asyncio

from athome import plugins

from . import common

TEST_DIR = '_testfiles'


class ModuleTest(unittest.TestCase):

    def setUp(self):
        if not os.path.exists(TEST_DIR):
            os.mkdir(TEST_DIR)
        for fnum in range(5):
            with open(TEST_DIR + '/file%d.py' % fnum,  'wb') as f:
                f.write(b'content')

    def tearDown(self):
        shutil.rmtree(TEST_DIR)

    def test_import_module(self):
        module = plugins._import_module('atestmodule', 'plugindir/heartbeat.py')
        self.assertEquals(types.ModuleType, type(module))

    def test_load_plugin_module(self):
        plugin = plugins._load_plugin_module('heartbeat.py', 'plugindir/heartbeat.py', None, 1234)
        self.assertEquals(plugins.Plugin, type(plugin))
        self.assertEquals(types.ModuleType, type(plugin.module))

    @unittest.expectedFailure
    def test_load_simple_module(self):
        plugin = plugins._load_plugin_module('heartbeat.py', 'test/test_plugins.py', None, 1234)
        
    def test_find_all(self):
        result = plugins._find_all(TEST_DIR)
        self.assertEquals(len(result), 5)
        self.assertEquals(len(result[0]), 2)

    def test_find_changed(self):
        all_files = plugins._find_all(TEST_DIR)
        with open(TEST_DIR + '/file1.py',  'wb') as f:
            f.write(b'tail')
        
        
