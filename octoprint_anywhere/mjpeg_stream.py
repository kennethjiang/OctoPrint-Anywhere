# coding=utf-8
from __future__ import absolute_import
from datetime import datetime, timedelta
import time
import logging
import StringIO
import re
import urllib2
from urlparse import urlparse
from contextlib import closing
import requests
import threading
from raven import breadcrumbs
import backoff
from .utils import ExpoBackoff

_logger = logging.getLogger('octoprint.plugins.anywhere')

class MjpegStream:

    def __init__(self):
        self._mutex = threading.RLock()
        self._should_quit = False

    def quit(self):
        with self._mutex:
            self._should_quit = True

    def should_quit(self):
        with self._mutex:
            return self._should_quit

    def stream_up(self, stream_host, token, printer, remote_status, settings, config):
        sentryClient = config.sentry

        class UpStream:
            def __init__(self, printer, settings, config):
                 self.settings = settings
                 self.config = config
                 self.last_reconnect_ts = datetime.now()
                 self.printer = printer
                 self.remote_status = remote_status
                 self.last_frame_ts = datetime.min

            def __iter__(self):
                return self

            def seconds_remaining_until_next_cycle(self):
                if self.remote_status['burst_count'] > 0:
                    self.remote_status['burst_count'] = self.remote_status['burst_count'] - 1
                    return 0

                cycle_in_seconds = 1.0/3.0 # Limit the bandwidth consumption to 3 frames/second
                if not self.printer.get_state_id() in ['PRINTING', 'PAUSED']:  # Printer idle
                    if self.remote_status['watching']:
                        cycle_in_seconds = 2
                    else:
                        cycle_in_seconds = 20
                else:
                    if not self.remote_status['watching']:
                        cycle_in_seconds = 10

                if not config.premium_video_eligible():
                    cycle_in_seconds *= config.mjpeg_stream_tier()
                else:
                    if not config.picamera_error():
                        cycle_in_seconds = 20

                return cycle_in_seconds - (datetime.now() - self.last_frame_ts).total_seconds()

            def next(self):
                if (datetime.now() - self.last_reconnect_ts).total_seconds() < 600: # Allow connection to last up to 600s
                    try:
                        while self.seconds_remaining_until_next_cycle() > 0:
                            time.sleep(0.1)

                        self.last_frame_ts = datetime.now()
                        return capture_mjpeg(self.settings)
                    except:
                        sentryClient.captureException()
                        raise StopIteration()
                else:
                    raise StopIteration()  # End connection so that `requests.post` can process server response


        backoff = ExpoBackoff(1200)

        while not self.should_quit():
            try:
                breadcrumbs.record(message="New UpStream: " + token)
                stream = UpStream(printer, settings, config)
                requests.post(stream_host + "/video/mjpegs", data=stream, headers={"Authorization": "Bearer " + token}).raise_for_status()
                backoff.reset()
            except Exception, e:
                _logger.error(e)
                backoff.more()


@backoff.on_exception(backoff.expo, Exception, max_value=1200)
@backoff.on_predicate(backoff.expo, max_value=1200)
def capture_mjpeg(settings):
    snapshot_url = settings.get("snapshot").strip()
    stream_url = settings.get("stream").strip()
    if snapshot_url:
        if not urlparse(snapshot_url).scheme:
            snapshot_url = "http://localhost/" + re.sub(r"^\/", "", snapshot_url)

        with closing(urllib2.urlopen(snapshot_url)) as res:
            jpg = res.read()
            return "--boundarydonotcross\r\nContent-Type: image/jpeg\r\nContent-Length: {0}\r\n\r\n{1}\r\n".format(len(jpg), jpg)

    elif stream_url:
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
