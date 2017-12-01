# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

import re

def normalize_path(path):
    normpath = re.sub(r'/+', '/', path)
    result = re.sub(r'(^/)|(/$)', '', normpath)
    return result

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

    def register(self, path, obj):
        chunks = self._chop(path)
        self._append(self.root, chunks, obj)

    def lookup(self, path):
        assert path is not None
        normalized_path, chunks = self._chop(path)
        assert len(chunks) > 0, 'insufficient path length'
        return self._lookup(self.root, chunks, normalized_path)

    def _lookup(self, node, chunks, original_path):
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
                    raise NameError('Can\'t find object at path')
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

    def _append(self, node, chunks, obj):
        remaining = len(chunks)
        assert remaining > 0
        current_chunk = chunks[0]
        print(current_chunk)
        if remaining == 1:
            if current_chunk not in node:
                print('append {}'.format(current_chunk))
                node[current_chunk] = obj
            else:
                raise Exception('node already exists {}'.format(current_chunk))
        else:
            if current_chunk not in node:
                node[current_chunk] = dict()
            elif not isinstance(node[current_chunk], dict):
                raise Exception('node already exists {}'.format(current_chunk))
            self._append(node[current_chunk], chunks[1:], obj)


