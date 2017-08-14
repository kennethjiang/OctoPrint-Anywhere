# coding=utf-8
from __future__ import absolute_import
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
from ratelimit import rate_limited

_logger = logging.getLogger(__name__)

@backoff.on_exception(backoff.expo, Exception, max_value=60)
@backoff.on_predicate(backoff.fibo, max_value=60)
def stream_up(q, cfg):
    class UpStream:
        def __init__(self, q):
             self.q = q
             self.cnt = 0

        def __iter__(self):
            return self

        @rate_limited(period=1, every=1.0)
        def next(self):
            self.cnt = self.cnt + 1;
            if self.cnt < 60:
                try:
                    return self.q.get(True, timeout=15.0)
                except Empty:
                    raise StopIteration()
            else:
                raise StopIteration()  # End connection so that `requests.post` can process server response

    while True:
        stream = UpStream(q)
        res = requests.post(cfg['api_host'] + "/app/video", data=stream, headers={"Authorization": "Bearer " + cfg['token']}).raise_for_status()


@backoff.on_exception(backoff.expo, Exception)
@backoff.on_predicate(backoff.fibo)
def capture_mjpeg(settings, q):
    snapshot_url = settings["snapshot"]
    if snapshot_url:
        if not urlparse(snapshot_url).scheme:
            snapshot_url = "http://localhost/" + re.sub(r"^\/", "", snapshot_url)

        while True:
            with closing(urllib2.urlopen(snapshot_url)) as res:
                jpg = res.read()
                data = "--boundarydonotcross\r\nContent-Type: image/jpeg\r\nContent-Length: {0}\r\n\r\n{1}\r\n".format(len(jpg), jpg)
                q.put(data)

    else:
        stream_url = settings["stream"]
        if not urlparse(stream_url).scheme:
            stream_url = "http://localhost/" + re.sub(r"^\/", "", stream_url)

        while True:
            with closing(urllib2.urlopen(stream_url)) as res:
                chunker = MjpegStreamChunker(q)

                data = res.readline()
                while not chunker.addLine(data):
                    data = res.readline()


class MjpegStreamChunker:

    def __init__(self, q):
        self.q = q
        self.boundary = None
        self.current_chunk = StringIO.StringIO()

    # Return: True: a new chunk is found.
    #         False: in the middle of the chunk
    def addLine(self, line):
        if not self.boundary:   # The first time addLine should be called with 'boundary' text as input
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

    capture_mjpeg("http://192.168.134.30:8080/?action=stream", q)
