# coding=utf-8
from __future__ import absolute_import
from datetime import datetime, timedelta
import time
import logging
import StringIO
import re
import urllib2
import urllib3
from urlparse import urlparse
import backoff
from contextlib import closing
import requests
from raven import breadcrumbs

_logger = logging.getLogger(__name__)

@backoff.on_exception(backoff.expo, Exception, max_value=1200)
@backoff.on_predicate(backoff.expo, max_value=1200)
def stream_up(stream_host, token, printer, remote_status, settings, sentryClient):
    class UpStream:
        def __init__(self, printer, settings):
             self.settings = settings
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

                    self.last_frame_ts = datetime.now()
                    return capture_mjpeg(self.settings)
                except urllib2.URLError:    # Caused by an invalid snapshot/stream url configuration. Expected for some users.
                    raise StopIteration()
                except Exception as e:
                    sentryClient.captureException()
                    raise StopIteration()
            else:
                raise StopIteration()  # End connection so that `requests.post` can process server response

    try:
        while True:
            breadcrumbs.record(message="New UpStream: " + token)
            stream = UpStream(printer, settings)
            requests.post(stream_host + "/video", data=stream, headers={"Authorization": "Bearer " + token}).raise_for_status()
    except Exception as e:
        if not isinstance(e, urllib3.exceptions.NewConnectionError):
            sentryClient.captureException()
        return False


def capture_mjpeg(settings):
    snapshot_url = settings.get("snapshot", None).strip()
    if snapshot_url:
        if not urlparse(snapshot_url).scheme:
            snapshot_url = "http://localhost/" + re.sub(r"^\/", "", snapshot_url)

        with closing(urllib2.urlopen(snapshot_url)) as res:
            jpg = res.read()
            return "--boundarydonotcross\r\nContent-Type: image/jpeg\r\nContent-Length: {0}\r\n\r\n{1}\r\n".format(len(jpg), jpg)

    else:
        stream_url = settings.get("stream", "/webcam/?action=stream").strip()
        if not urlparse(stream_url).scheme:
            stream_url = "http://localhost/" + re.sub(r"^\/", "", stream_url)

        with closing(urllib2.urlopen(stream_url)) as res:
            chunker = MjpegStreamChunker()

            while True:
                data = res.readline()
                mjpg = chunker.findMjpegChunk(data)
                if mjpg:
                    res.close()
                    return mjpg


class MjpegStreamChunker:

    def __init__(self):
        self.boundary = None
        self.current_chunk = StringIO.StringIO()

    # Return: mjpeg chunk if found
    #         None: in the middle of the chunk
    def findMjpegChunk(self, line):
        if not self.boundary:   # The first time endOfChunk should be called with 'boundary' text as input
            self.boundary = line
            self.current_chunk.write(line)
            return None

        if len(line) == len(self.boundary) and line == self.boundary:  # start of next chunk
            return self.current_chunk.getvalue()

        self.current_chunk.write(line)
        return None
