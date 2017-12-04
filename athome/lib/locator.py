# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

import re
import logging

LOGGER = logging.getLogger(__name__)


def normalize_path(path):
    normpath = re.sub(r'/+', '/', path)
    result = re.sub(r'(^/)|(/$)', '', normpath)
    return result


class NameError(Exception):
    pass


class Cache:

    root = dict()
    __instance = None
    __initialiazed = False


    def __new__(cls, factory=None):
        if cls.__instance is None:
            cls.__instance = object.__new__(cls)
        return cls.__instance


    def __init__(self, factory=None):
        if not Cache.__initialiazed:
            self.factory = factory
            Cache.__initialiazed = True


    def lookup(self, path):
        assert path is not None
        normalized_path, chunks = self._chop(path)
        assert len(chunks) > 0, 'insufficient path length'
        return self._lookup(self.root, chunks, normalized_path)


    def _lookup(self, node, chunks, original_path):
        if LOGGER.isDebugEneabled():
            LOGGER.debug(node)
            LOGGER.debug(chunks)
            LOGGER.debug(original_path)
        first, remaining = chunks[0], chunks[1:]
        current_node = node.get(first)
        if not remaining:
            if current_node:
                result = current_node
            else:
                if self.factory:
                    result = self.factory.new(original_path)
                    self.register(original_path, result)
                else:
                    raise NameError(
                        'Can\'t find object at path {}'.format(original_path))
        else:
            if not current_node:
                current_node = dict()
                node[first] = current_node
            result = self._lookup(current_node, remaining, original_path)
        return result


    @staticmethod
    def _chop(path):
        normalized_path = normalize_path(path)
        return normalized_path, normalized_path.split('/')


    def register(self, path, obj):
        chunks = self._chop(path)
        self._append(self.root, chunks, obj)


    def _append(self, node, chunks, obj):
        LOGGER.debug('_append %s, %s, %s', node, chunks, obj)
        first, remaining = chunks[0], chunks[1:]
        if remaining:
            if first not in node:
                node[first] = dict()
            elif not isinstance(node[first], dict):
                raise Exception('node already exists {}'.format(first))
            self._append(node[first], remaining, obj)
        else:
            if first not in node:
                LOGGER.debug('append %s', first)
                node[first] = obj
            else:
                raise Exception('node already exists {}'.format(first))



if __name__ == '__main__':
    global LOGGER
    logging.basicConfig(level=logging.DEBUG)
    LOGGER = logging.getLogger(__name__)
    C = Cache()
    C.register('as/asd', 1)

