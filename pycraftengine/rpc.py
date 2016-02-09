# -*- coding: utf-8 -*-
__author__ = "Alexey Kachalov"

import threading
import select
import socket
import logging
import time
import traceback

from multiprocessing.dummy import Pool as ThreadPool
from ddp import DdpSocket

from .exceptions import KernelException

logger = logging.getLogger("craftengine")
logger.setLevel("DEBUG")


class Proxy:
    def __init__(self, rpc, node=None, service=None, instance=None, name=None, callback=None, sync=None):
        self.rpc = rpc
        self.name = name
        self.callback = callback
        self.sync = sync
        self.node = "__localhost__" if node is None else node
        self.service = service
        self.instance = None if instance is None else int(instance)

    def __getattr__(self, name):
        self.name = name if self.name is None else "%s.%s" % (self.name, name)
        return self

    def __call__(self, *args, **kwargs):
        if self.name is None:
            raise ValueError("Proxy class is not callable")
        logger.debug("Proxy call: `%s`: %s on `%s`" % (self.service, self.name, self.node))
        return self.rpc.exec(
            self.node,
            self.service,
            self.instance,
            self.name,
            args,
            kwargs,
            self.callback,
            self.sync,
        )


class Service(object):
    def __init__(self, rpc, service, node, instance):
        self.rpc = rpc
        self.service = service
        self.node = "__local__" if node is None else node
        self.instance = None if instance is None else int(instance)

    def sync_callback(self, response, identificator):
        logger.debug("sync_callback(%s, %s)" % (response, identificator))
        self.rpc.sync_data[identificator] = response

    def sync_callback_error(self, response, identificator):
        logger.debug("sync_callback_error(%s, %s)" % (response, identificator))
        self.rpc.sync_data[identificator] = KernelException(response)

    def _get_proxy(self, callback=None, sync=None):
        return Proxy(
            self.rpc,
            node=self.node,
            service=self.service,
            instance=self.instance,
            name=None,
            callback=callback,
            sync=sync,
        )

    def sync(self):
        return self._get_proxy((self.sync_callback, self.sync_callback_error), True)

    def async(self, callback=None):
        return self._get_proxy(callback, False)


class Rpc(object):
    RECONN_TIMES = 12
    RECONN_DELAY = 5

    def __init__(self, service, instance, address, token, threads=None, params=None):
        self.service = service
        self.instance = instance
        self.address = address
        self.token = token
        self.threads = 1 if threads is None else int(threads)
        self.workers = ThreadPool(self.threads)
        self.params = {} if params is None else dict(params)

        self._requests = {}
        self._send_data = {}
        self.sockets = {}
        self.alive = True
        self.ready = {}
        self.binds = {}
        self.epoll = select.epoll()
        self.sync_data = {}

    def __call__(self, service, node=None, instance=None):
        return Service(self, service, node, instance)

    def create_socket(self):
        logger.debug("Creating socket")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        for _ in range(self.RECONN_TIMES):
            try:
                sock.connect(self.address)
            except ConnectionRefusedError:
                logger.debug("Trying to connect...")
                time.sleep(self.RECONN_DELAY)
            else:
                sock.setblocking(False)
                self.sockets[sock.fileno()] = sock
                self.epoll.register(sock.fileno(), select.EPOLLIN)
                self.ready[sock.fileno()] = False
                self.auth(sock.fileno())
                break

    def serve(self):
        logger.debug("Starting RPC...")
        for i in range(self.threads):
            self.create_socket()

        try:
            while self.alive:
                events = self.epoll.poll(1)
                for fileno, event in events:
                    if fileno in self.sockets.keys():
                        sock = self.sockets[fileno]
                        if event & select.EPOLLIN:
                            self.recv(sock)
                        elif event & select.EPOLLOUT:
                            self.send(sock)
                        elif event & select.EPOLLHUP:
                            self.close(sock)
        finally:
            self.close()
            if self.alive:
                self.serve()

    def send(self, sock):
        logger.debug("Send")
        try:
            data = self._send_data[sock.fileno()].pop(0)
            DdpSocket().encode(data, socket=sock)
        except IndexError:
            self.close(sock)
        self.epoll.modify(sock.fileno(), select.EPOLLIN)

    def recv(self, sock):
        logger.debug("Recv")
        try:
            data = DdpSocket.decode(sock)
            try:
                self.parse_data(data)
            except Exception as e:
                logger.exception(e)
        except IndexError:
            self.close(sock)

    def parse_data(self, data):
        case = data.pop(0)
        if case == "request":
            self.process_request(data)
        elif case == "response":
            try:
                self.process_response(data)
            except Exception as e:
                logger.exception(e)
        else:
            logger.error("Unexpected case: %s" % case)

    def process_request(self, data):
        identificator = None
        error = None
        result = None
        try:
            (node, service, instance), method, args, kwargs, identificator = data
            callback = self.binds[method]
            result = callback(*args, **kwargs)
        except Exception as e:
            error = [
                "%s.%s" % (getattr(e, "__module__", "__built_in__"), e.__class__.__name__),
                str(e),
                traceback.format_exc(),
            ]
            logger.exception(e)

        if identificator:
            response = [
                "response",
                result,
                error,
                identificator,
            ]

            self._send(response)

    def process_response(self, data):
        response, error, identificator = data
        callback, callback_error = self._requests[identificator]
        if error is None:
            callback(response, identificator)
        else:
            callback_error(error, identificator)

    def close(self, sock=None):
        if sock is None:
            logger.debug("Stopping RPC...")
        sockets = self.sockets if sock is None else {sock.fileno(): sock}
        for fileno, sock in sockets.copy().items():
            self.epoll.unregister(fileno)
            del self.sockets[fileno]
            sock.close()
        self.alive = False

    def _send(self, data, fileno=None):
        # TODO
        fileno = list(self.sockets.keys())[0] if fileno is None else int(fileno)
        try:
            self._send_data[fileno].append(data)
        except KeyError:
            self._send_data[fileno] = [data]
        try:
            self.epoll.modify(fileno, select.EPOLLOUT)
        except FileNotFoundError as e:
            logger.exception(e)

    def auth(self, fileno=None):
        fileno = list(self.sockets.keys()) if fileno is None else fileno
        fileno = fileno if isinstance(fileno, list) else [fileno]
        for fn in fileno:
            request = [
                "connect",
                [
                    self.service,
                    self.instance,
                ],
                self.token,
                self.params,
            ]
            self._send(request, fn)
            self.ready[fn] = True

    def generate_id(self):
        return "%s" % (time.time())

    def exec(self, node, service, instance, method, args=None, kwargs=None, callback=None, sync=None):
        while (False in self.ready.values() or len(self.ready) == 0) and self.alive:
            time.sleep(0.1)

        if not self.alive:
            return

        args = () if args is None else args
        kwargs = {} if kwargs is None else kwargs
        identificator = None if callback is None else self.generate_id()
        sync = False if sync is None else True
        request = [
            "request",
            [
                node,
                service,
                instance,
            ],
            method,
            args,
            kwargs,
            identificator,
        ]

        if identificator is not None:
            self._requests[identificator] = callback

        self._send(request)
        if sync:
            while self.alive and identificator not in self.sync_data.keys():
                time.sleep(0.01)

            if not self.alive:
                return

            response = self.sync_data[identificator]
            if isinstance(response, Exception):
                raise response
            else:
                return response
        else:
            return identificator

    def bind(self, method, callback):
        self.binds[method] = callback
