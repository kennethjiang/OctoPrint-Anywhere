# coding=utf-8
from __future__ import absolute_import
import time
import random
import re
import os
import tempfile

CAM_EXCLUSIVE_USE = os.path.join(tempfile.gettempdir(), '.using_picam')

def ip_addr():
    ip_addresses = []
    try:
        from subprocess import check_output
        ip_addresses = check_output(['hostname', '--all-ip-addresses']).split()
    except:
        pass

    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    try:
        s.connect(('10.255.255.255', 1))
    except:
        s.connect(("8.8.8.8", 53))   # None of these 2 ways are 100%. Double them to maximize the chance

    primary_ip = s.getsockname()[0]
    s.close()

    if primary_ip not in ip_addresses:
        ip_addresses.append(primary_ip)

    return ip_addresses

def pi_version():
    try:
        with open('/sys/firmware/devicetree/base/model', 'r') as firmware_model:
            return re.search('Raspberry Pi(.*)', firmware_model.read()).group(1)
    except:
         return None

class ExpoBackoff:

    def __init__(self, max_seconds):
        self.attempts = -3
        self.max_seconds = max_seconds

    def reset(self):
        self.attempts = -3

    def more(self):
        self.attempts += 1
        delay = 2 ** self.attempts
        if delay > self.max_seconds:
            delay = self.max_seconds
        delay *= 0.5 + random.random()
        time.sleep(delay)


def not_using_pi_camera():
    try:
        os.remove(CAM_EXCLUSIVE_USE)
    except:
        pass

def using_pi_camera():
    open(CAM_EXCLUSIVE_USE, 'a').close()  # touch CAM_EXCLUSIVE_USE to indicate the intention of exclusive use of pi camera
