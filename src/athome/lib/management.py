# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

import inspect

import json


def managed(f):
    setattr(f, '__managed_method', True)
    return f


class ManagedObject:

    def __init__(self, obj):
        self.obj = obj
        self._managed_class = obj.__class__
        self._read_properties = set()
        self._write_properties = set()
        self._methods = dict()
        props = inspect.getmembers(self._managed_class, 
                                   lambda m: isinstance(m, property)
                                  )
        for name, prop in props:
            if prop.fget:
                self._read_properties.add(name)
            if prop.fset:
                self._write_properties.add(name)
        
        meths = inspect.getmembers(self.obj, inspect.ismethod)
        for name, meth in meths:
            if getattr(meth, '__managed_method', False):
                spec = inspect.getfullargspec(meth)
                assert not spec.varargs, 'varargs not allowed in managed methods'
                assert not spec.varkw, 'varkw not allowed in managed methods'
                assert not spec.kwonlyargs, 'kwonlyargs not allowed in managed methods'
                self._methods[name] = spec.args[1:]

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
        assert method in self._methods
        return getattr(self.obj, method)(*args)

    def json(self):
        result = dict()
        descriptor = dict()
        descriptor['class'] = self._managed_class.__name__
        descriptor['read_properties'] = list(self._read_properties)
        descriptor['write_properties'] = list(self._write_properties)
        descriptor['methods'] = self._methods

        result['__description'] = descriptor
        for prop in self._read_properties:
            result[prop] = self.get_property(prop)
        return json.dumps(result)


class A():

    def __init__(self):
        super().__init__()
        self._val = 0
        self.minchia = 3

    @managed
    def sayminchia(self):
        print(self.minchia)

    @property
    def x(self):
        return self._val

    @x.setter
    def x(self, value):
        self._val = value

    @x.deleter
    def x(self):
        del self._val



if __name__ == '__main__':
    a = A()
    ma = ManagedObject(a)
    print(ma.json())
    print(ma.invoke('sayminchia'))

