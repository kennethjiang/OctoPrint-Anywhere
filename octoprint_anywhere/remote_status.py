# coding=utf-8
from __future__ import absolute_import
import threading

class RemoteStatus:

    def __init__(self):
        self._mutex = threading.RLock()
        self.__items__ = {"watching": False}

    def __getitem__(self, key):
        with self._mutex:
            return self.__items__[key]

    def __setitem__(self, key, value):
        with self._mutex:
            self.__items__[key] = value
