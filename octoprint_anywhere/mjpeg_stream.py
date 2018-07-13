# coding=utf-8
from __future__ import absolute_import
from datetime import datetime, timedelta
import time
from Queue import Queue
from Queue import Empty
from threading import Thread
import logging
import StringIO
import re
import urllib2
from urlparse import urlparse
import backoff
from contextlib import closing
import requests

_logger = logging.getLogger(__name__)

@backoff.on_exception(backoff.expo, Exception, max_value=60)
@backoff.on_predicate(backoff.fibo, max_value=60)
def stream_up(q, cfg, printer, remote_status):
    class UpStream:
        def __init__(self, q, printer):
             self.q = q
             self.last_reconnect_ts = datetime.now()
             self.printer = printer
             self.remote_status = remote_status
             self.last_frame_ts = datetime.min

        def __iter__(self):
            return self

        def seconds_remaining_until_next_cycle(self):
            cycle_in_seconds = 1.0/3.0 # Limit the bandwidth consumption to 3 frames/second
            if not self.printer.get_state_id() in ['PRINTING', 'PAUSED']:  # Printer idle
                if self.remote_status['watching']:
                    cycle_in_seconds = 2
                else:
                    cycle_in_seconds = 20
            else:
                if not self.remote_status['watching']:
                    cycle_in_seconds = 10
            return cycle_in_seconds-(datetime.now() - self.last_frame_ts).total_seconds()


        def next(self):
            if (datetime.now() - self.last_reconnect_ts).total_seconds() < 60: # Allow connection to last up to 60s
                try:
                    while self.seconds_remaining_until_next_cycle() > 0:
                        time.sleep(0.1)

                    print(self.remote_status)
                    self.last_frame_ts = datetime.now()
                    return self.q.get(True, timeout=15.0)
                except Empty:
                    raise StopIteration()
            else:
                raise StopIteration()  # End connection so that `requests.post` can process server response

    while True:
        stream = UpStream(q, printer)
        res = requests.post(cfg['stream_host'] + "/video", data=stream, headers={"Authorization": "Bearer " + cfg['token']}).raise_for_status()


@backoff.on_exception(backoff.expo, Exception)
@backoff.on_predicate(backoff.fibo)
def capture_mjpeg(settings, q):
    snapshot_url = settings.get("snapshot", None)
    if snapshot_url:
        if not urlparse(snapshot_url).scheme:
            snapshot_url = "http://localhost/" + re.sub(r"^\/", "", snapshot_url)

        while True:
            with closing(urllib2.urlopen(snapshot_url)) as res:
                jpg = res.read()
                data = "--boundarydonotcross\r\nContent-Type: image/jpeg\r\nContent-Length: {0}\r\n\r\n{1}\r\n".format(len(jpg), jpg)
                q.put(data)

    else:
        stream_url = settings.get("stream", "/webcam/?action=stream")
        if not urlparse(stream_url).scheme:
            stream_url = "http://localhost/" + re.sub(r"^\/", "", stream_url)

        while True:
            with closing(urllib2.urlopen(stream_url)) as res:
                chunker = MjpegStreamChunker(q)

                data = res.readline()
                while not chunker.endOfChunk(data):
                    data = res.readline()


class MjpegStreamChunker:

    def __init__(self, q):
        self.q = q
        self.boundary = None
        self.current_chunk = StringIO.StringIO()

    # Return: True: a new chunk is found.
    #         False: in the middle of the chunk
    def endOfChunk(self, line):
        if not self.boundary:   # The first time endOfChunk should be called with 'boundary' text as input
            self.boundary = line
            self.current_chunk.write(line)
            return False

        if len(line) == len(self.boundary) and line == self.boundary:  # start of next chunk
            self.q.put(self.current_chunk.getvalue())
            self.current_chunk = StringIO.StringIO()
            return True

        self.current_chunk.write(line)
        return False


if __name__ == "__main__":
    class ConfigStub:
        def __init__(self, path):
            self.p = path

        def load_config(self):
            import yaml
            with open(self.p, 'r') as stream:
                return yaml.load(stream)

    import logging
    logging.basicConfig()
    logging.getLogger().setLevel(logging.DEBUG)
    req_log = logging.getLogger('requests.packages.urllib3')
    req_log.setLevel(logging.DEBUG)
    req_log.propagate = True
    import sys

    q = Queue(maxsize=1)

    upstream_thread = Thread(target=stream_up, args=(q,ConfigStub(sys.argv[1]).load_config()))
    upstream_thread.daemon = True
    upstream_thread.start()

    capture_mjpeg(ConfigStub(sys.argv[1]).load_config()["webcam"], q)
