# -*- coding: utf-8 -*-
__author__ = "Alexey Kachalov"

import os
import time
import traceback
import logging
import signal

from craftengine.exceptions import KernelException
from craftengine.rpc import Rpc

logging.basicConfig(format="[%(threadName)s][%(asctime)-15s] %(message)s")
logger = logging.getLogger("craftengine")
logger.setLevel("DEBUG")

rpc = None


def main():
    global rpc
    signal.signal(signal.SIGTERM, exit)
    signal.signal(signal.SIGINT, exit)
    signal.signal(signal.SIGPWR, exit)

    plugin, token = os.environ.get("CE_NAME", ""), os.environ.get("CE_TOKEN", "")
    host, port = "ce-kernel", 5000

    print("="*20)
    print("Test app")
    print("Name:", plugin)
    print("Token:", token)
    print("Sever: %s:%i" % (host, port))
    print("="*20)

    rpc = Rpc((host, port), (plugin, token))
    logger.debug("Connecting to server...")

    rpc.bind("test", lambda: "CLI: " + str(time.time()))
    rpc.bind("event.callback", lambda name, data: None)

    rpc.sync_exec.event.register("test", "test")
    x = 1000
    b = time.time()
    n = 0
    for i in range(x):
        rpc.sync_exec.event.initiate("test")
        if (time.time() - b) // 10 > n:
            n = (time.time() - b) // 10
            print("%0.2fs reqs: %i" % (time.time() - b, i))
    e = time.time()
    print("requests: %i | rps: %0.3f" % (x, x/(e-b)))
    while True:
        try:
            print(rpc.sync_exec.kernel.env())
        except KernelException as e:
            print(traceback.format_list(e.tb))
            print(e.exc + ":", e.value)
        time.sleep(2)


def exit(*args, **kwargs):
    global rpc
    logger.debug("Stopping...")
    rpc.close()

if __name__ == "__main__":
    main()
