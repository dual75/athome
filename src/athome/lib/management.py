# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

import asyncio
import inspect
import logging
import functools
import json

from collections import namedtuple
MethodInfo = namedtuple('MethodInfo', ('orig_name', 'params'))

LOGGER = logging.getLogger(__name__)

def managed(name=None):

    def wrap_coro(decorated_coro):
        assert asyncio.iscoroutinefunction(decorated_coro)
        decorated_coro._managed_method = name or func.__name__
        return decorated_coro

    return wrap_coro


class ManagedObject:

    def __init__(self, obj):
        self.obj = obj
        self._managed_class = obj.__class__
        self._read_properties = set()
        self._write_properties = set()
        self.methods = dict()
        props = inspect.getmembers(self._managed_class, lambda m: isinstance(m, property))
        for name, prop in props:
            if prop.fget:
                self._read_properties.add(name)
            if prop.fset:
                self._write_properties.add(name)
        
        meths = inspect.getmembers(self.obj, asyncio.iscoroutinefunction)
        for name, meth in meths:
            LOGGER.debug('analyze method: %s', name)
            managed_name = getattr(meth, 'managed', None)
            if managed_name:
                spec = inspect.getfullargspec(meth)
                assert not spec.varargs, 'varargs not allowed in managed methods'
                assert not spec.varkw, 'varkw not allowed in managed methods'
                assert not spec.kwonlyargs, 'kwonlyargs not allowed in managed methods'
                self.methods[managed_name] = MethodInfo(name, spec.args[1:])

    @property
    def read_properties(self):
        return self._read_properties

    @property
    def write_properties(self):
        return self._write_properties

    def get_property(self, prop):
        assert prop in self._read_properties
        return getattr(self.obj, prop)

    def set_property(self, prop, value):
        assert prop in self._write_properties
        setattr(self.obj, prop, value)

    def invoke(self, method, args=list()):
        assert method in self.methods
        return getattr(self.obj, self.methods[method].orig_name)(*args)

    async def async_invoke(self, method, args=list()):
        assert method in self.methods
        return await getattr(self.obj, self.methods[method].orig_name)(*args)

    def json(self):
        result = dict()
        meta = dict()
        meta['class'] = self._managed_class.__name__
        meta['read_properties'] = list(self._read_properties)
        meta['write_properties'] = list(self._write_properties)
        meta['methods'] = {name: method.params for name, method in self.methods.items()}

        result['__meta'] = meta
        for prop in self._read_properties:
            result[prop] = self.get_property(prop)
        return json.dumps(result)
