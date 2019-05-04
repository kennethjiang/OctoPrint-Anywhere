# coding=utf-8
from __future__ import absolute_import
import time
import random
import re

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
    """Detect the version of the Raspberry Pi.  Returns either 1, 2 or
    None depending on if it's a Raspberry Pi 1 (model A, B, A+, B+),
    Raspberry Pi 2 (model B+), or not a Raspberry Pi.
    """
    # Check /proc/cpuinfo for the Hardware field value.
    # 2708 is pi 1
    # 2709 is pi 2
    # 2835 is pi 3 on 4.9.x kernel
    # Anything else is not a pi.
    with open('/proc/cpuinfo', 'r') as infile:
        cpuinfo = infile.read()
    # Match a line like 'Hardware   : BCM2709'
    match = re.search('^Hardware\s+:\s+(\w+)$', cpuinfo,
                      flags=re.MULTILINE | re.IGNORECASE)
    if not match:
        # Couldn't find the hardware, assume it isn't a pi.
        return None
    if match.group(1) == 'BCM2708':
        # Pi 1
        return 1
    elif match.group(1) == 'BCM2709':
        # Pi 2
        return 2
    elif match.group(1) == 'BCM2835':
        # Pi 3 / Pi on 4.9.x kernel
        return 3
    else:
        # Something else, not a pi.
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
