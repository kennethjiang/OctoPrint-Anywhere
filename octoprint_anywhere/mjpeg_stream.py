# coding=utf-8
from __future__ import absolute_import
from Queue import Queue
from threading import Thread
import StringIO
import re
import urllib2
from urlparse import urlparse
import backoff

@backoff.on_exception(backoff.expo, Exception)
@backoff.on_predicate(backoff.fibo)
def capture_mjpeg(q, stream_url):
    if not urlparse(stream_url).scheme:
        stream_url = "http://localhost/" + re.sub(r"^\/", "", stream_url)

    try:
        res = urllib2.urlopen(stream_url)
        data = res.readline()

        chunker = MjpegStreamChunker(q)

        while(data):
            chunker.addLine(data)
            data = res.readline()

    finally:
        try:
            res.close()
        except NameError:
            pass

class MjpegStreamChunker:

    def __init__(self, q):
        self.q = q
        self.boundary = None
        self.current_chunk = StringIO.StringIO()

    def addLine(self, line):
        if not self.boundary:   # The first time addLine should be called with 'boundary' text as input
            self.boundary = line

        if line == self.boundary:  # start of next chunk
            self.q.put(self.current_chunk.getvalue())
            self.current_chunk = StringIO.StringIO()

        self.current_chunk.write(line)


if __name__ == "__main__":
    q = Queue()
    producer = Thread(target=capture_mjpeg, args=(q,"http://192.168.134.30:8080/?action=stream"))
    producer.daemon = True
    producer.start()
    with open("/tmp/test.out", 'w') as f:
        while True:
            last_chunk = q.get()
            f.write(last_chunk)
            import time
            time.sleep(1)
            f.flush()

