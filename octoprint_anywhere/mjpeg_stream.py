# coding=utf-8
from __future__ import absolute_import
from Queue import Queue
from threading import Thread
import StringIO
import re
import urllib2
from urlparse import urlparse
import backoff
from contextlib import closing

@backoff.on_exception(backoff.expo, Exception)
@backoff.on_predicate(backoff.fibo)
def capture_mjpeg(q, stream_url):
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

