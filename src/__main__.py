# -*- coding: utf-8 -*-
__author__ = "Alexey Kachalov"

import os
import time
import traceback
import logging

from craftengine.exceptions import KernelException
from craftengine.rpc import Rpc

logging.basicConfig(format="[%(threadName)s][%(asctime)-15s] %(message)s")
logger = logging.getLogger("craftengine")
logger.setLevel("DEBUG")

if __name__ == "__main__":
    print("="*20)
    print("Test app")
    print("="*20)

    plugin, token = os.environ.get("CE_NAME", ""), os.environ.get("CE_TOKEN", "")

    rpc = Rpc(("ce-kernel", 5000), (plugin, token))
    logger.debug("Connecting to server...")

    rpc.bind("test", lambda: "CLI: " + str(time.time()))

    while True:
        try:
            print(rpc.sync_exec.kernel.env())
        except KernelException as e:
            print(traceback.format_list(e.tb))
            print(e.exc + ":", e.value)
        time.sleep(2)
    rpc.close()
