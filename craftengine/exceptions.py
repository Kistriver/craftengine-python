# -*- coding: utf-8 -*-
__author__ = "Alexey Kachalov"


import traceback


class KernelException(Exception):
    def __init__(self, value=None, exc=None, tb=None):
        self.value = "" if value is None else value
        self.tb = traceback.extract_tb(self.__traceback__) if tb is None else tb
        self.exc = "KernelException" if exc is None else exc
