# -*- coding: utf-8 -*-
__author__ = "Alexey Kachalov"

import threading
import select
import socket
import logging
import time
import traceback
from ddp import DdpSocket

from .exceptions import KernelException

logger = logging.getLogger("craftengine")
logger.setLevel("CRITICAL")


class Rpc(object):
    RECONN_TIMES = 12
    RECONN_DELAY = 5

    STREAMIN = select.EPOLLIN
    STREAMOUT = select.EPOLLOUT
    streamst = STREAMIN

    def __init__(self, server_address, token):
        self.alive = True
        self._ready = False
        self._methods = {}
        self._sync = {}
        self.server_address = server_address
        self.token = token
        self.serializer = DdpSocket()
        self._requests = {}
        self._responses = []
        self.socket = None
        self.epoll = select.epoll()
        threading.Thread(target=self.serve, name="CE-RPC").start()

    def close(self):
        logger.debug("Closing connection...")
        self.alive = False
        try:
            self.epoll.unregister(self.socket.fileno())
            self.socket.close()
        except:
            logger.exception("Server closed incorrectly")

    def serve(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        for _ in range(self.RECONN_TIMES):
            try:
                self.socket.connect(self.server_address)
                break
            except ConnectionRefusedError:
                logger.debug("Trying to connect...")
                time.sleep(self.RECONN_DELAY)
        self.socket.setblocking(False)
        self.epoll.register(self.socket.fileno(), select.EPOLLIN)
        self._ready = True

        self.async_exec().kernel.auth(*self.token)

        try:
            while self.alive:
                events = self.epoll.poll(1)
                for fileno, event in events:
                    if fileno == self.socket.fileno():
                        if event & select.EPOLLIN:
                            self.epollin()
                        elif event & select.EPOLLOUT:
                            self.epollout()
                        elif event & select.EPOLLHUP:
                            self.epollhup()
        except KernelException:
            self.serve()
        except:
            self.close()
            if self.alive:
                logger.exception("Exception has thrown: restarting")
                self.__init__(self.server_address, self.token)
        self.close()

    def epollin(self):
        try:
            data = self.serializer.decode(self.socket)
            logger.debug(data)
            if len(data) == 4:
                response = self._request(data)
                if response is None:
                    return
                else:
                    self._responses.append(response)
            else:
                self._response(data)
                return
        except KernelException:
            raise
        except:
            logger.exception("")
            self.close()
        self.stream(self.STREAMOUT)

    def epollout(self):
        try:
            while len(self._responses) > 0:
                r = self._responses[0]
                del self._responses[0]
                try:
                    logger.debug(self.serializer.encode(r, socket=self.socket))
                except:
                    logger.exception("")
                    self.close()
            self.stream(self.STREAMIN)
        except:
            logger.exception("")

    def epollhup(self):
        self.close()

    def stream(self, sttype):
        st = self.streamst
        self.streamst = sttype
        try:
            self.epoll.modify(self.socket.fileno(), sttype)
        except OSError:
            self.close()
        return st

    def _exec(self, method, args=None, kwargs=None, callback=None, sync=None):
        args = () if args is None else args
        kwargs = {} if kwargs is None else kwargs
        identificator = None if callback is None else time.time()
        sync = False if sync is None else sync
        request = [
            method,
            args,
            kwargs,
            identificator,
        ]
        logger.debug(str(request))

        if identificator is not None:
            self._requests[identificator] = callback

        self._responses.append(request)
        self.stream(self.STREAMOUT)

        if sync:
            while identificator not in self._sync.keys() and self.alive:
                time.sleep(0.001)

            if not self.alive:
                raise KernelException("Exited")

            r = self._sync[identificator]
            if isinstance(r, Exception):
                raise r
            else:
                return r
        else:
            return identificator

    @property
    def sync_exec(self):
        while not self._ready:
            time.sleep(0.01)

        def cb(data, identificator):
            self._sync[identificator] = data

        def eh(err, identificator):
            self._sync[identificator] = KernelException(*err)

        return Proxy(self, callback=(cb, eh), sync=True)

    def async_exec(self, callback=None):
        while not self._ready:
            time.sleep(0.01)

        return Proxy(self, callback=callback, sync=False)

    def _request(self, data):
        identificator = None
        try:
            method, args, kwargs, identificator = data[:4]

            function = self._methods[method]
            function.__globals__["request"] = self
            data = function(*args, **kwargs)
        except Exception as e:
            error = ["%s.%s" % (getattr(e, "__module__", "__built_in__"), e.__class__.__name__), str(e), traceback.extract_tb(e.__traceback__)]
            data = []
            logger.exception(e)
        else:
            error = []

        if identificator is None:
            return None

        return identificator, error, data

    def _response(self, data):
        try:
            callback = self._requests[data[0]]
        except KeyError:
            logger.debug("Callback not found")
            return

        def err_handler(err, identificator):
            raise KernelException(*err)

        if isinstance(callback, tuple):
            callback, err_handler = callback

        if len(data[1]) == 0:
            try:
                callback(data[2], data[0])
            except:
                logger.exception("Could not process response")
        else:
            err_handler(data[1], data[0])

    def bind(self, name, method=None):
        def wrapper(f):
            _add(name, f)

            def wrap(*args, **kwargs):
                return f(*args, **kwargs)
            return wrap

        def _add(name, method):
            self._methods[name] = method

        if method is not None:
            _add(name, method)
        else:
            return wrapper


class Proxy:
    def __init__(self, rpc, name=None, callback=None, sync=None):
        self.rpc = rpc
        self.name = name
        self.callback = callback
        self.sync = sync

    def __getattr__(self, name):
        nn = name if self.name is None else "%s.%s" % (self.name, name)
        logger.debug("Proxy get: %s" % nn)
        return Proxy(self.rpc, name=nn, callback=self.callback, sync=self.sync)

    def __call__(self, *args, **kwargs):
        if self.name is None:
            raise ValueError("Proxy class is not callable")
        logger.debug("Proxy call: %s" % self.name)
        return self.rpc._exec(self.name, args, kwargs, callback=self.callback, sync=self.sync)
