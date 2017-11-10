# Copyright (c) 2017 Alessandro Duca
#
# See the file license.txt for copying permission.

"""
"""

import os
import unittest

import asyncio

from athome import plugins

from . import common


class PluginManagerTest(unittest.TestCase):
    """Test plugins broker setup"""

    def test_plugin_manager_singleton(self):
        """Check that PluginManager is actually a singleton"""
        
        manager1 = plugins.PluginManager()
        manager2 = plugins.PluginManager()
        self.assertIs(manager1, manager2)


class PluginManagerTest(unittest.TestCase):
    """Test plugins broker setup"""

    def test_plugin_manager_singleton(self):
        """Check that PluginManager is actually a singleton"""
        
        manager1 = plugins.PluginManager()
        manager2 = plugins.PluginManager()
        self.assertIs(manager1, manager2)
        
