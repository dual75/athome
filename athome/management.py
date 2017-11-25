# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

class ManagementMixin:

    def __init__(self, parent):
        self.parent = parent
        self.children = dict()


