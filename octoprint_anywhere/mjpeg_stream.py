# coding=utf-8
from __future__ import absolute_import
from datetime import datetime, timedelta
import time
import sys
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

    def stream_up(self, stream_host, token, printer, remote_status, settings, config):
        sentryClient = config.sentry
        last_frame_ts = datetime.min

        def seconds_remaining_until_next_cycle():
            if remote_status['burst_count'] > 0:
                remote_status['burst_count'] = remote_status['burst_count'] - 1
                return 0

            cycle_in_seconds = 1.0/3.0 # Limit the bandwidth consumption to 3 frames/second
            if not printer.get_state_id() in ['PRINTING', 'PAUSED']:  # Printer idle
                if remote_status['watching']:
                    cycle_in_seconds = 2
                else:
                    cycle_in_seconds = 20
            else:
                if not remote_status['watching']:
                    cycle_in_seconds = 10

            if not config.premium_video_eligible():
                cycle_in_seconds *= config.mjpeg_stream_tier()
            else:
                if not config.picamera_error():
                    cycle_in_seconds = 20

            cycle_in_seconds = min(cycle_in_seconds, 20)

            return cycle_in_seconds - (datetime.now() - last_frame_ts).total_seconds()

        backoff = ExpoBackoff(1200)

        while True:
            try:
                while seconds_remaining_until_next_cycle() > 0:
                    time.sleep(0.1)

                last_frame_ts = datetime.now()
                jpg = capture_mjpeg(settings)
                r = requests.post(stream_host+'/video/jpgs', files=dict(jpg=jpg), headers={"Authorization": "Bearer " + token})
                r.raise_for_status()
                backoff.reset()
            except Exception, e:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                _logger.error(e)
                backoff.more()


@backoff.on_exception(backoff.expo, Exception, max_value=1200)
@backoff.on_predicate(backoff.expo, max_value=1200)
def capture_mjpeg(settings):
    snapshot_url = settings.get("snapshot", '').strip()
    stream_url = settings.get("stream", '').strip()
    if snapshot_url:
        if not urlparse(snapshot_url).scheme:
            snapshot_url = "http://localhost/" + re.sub(r"^\/", "", snapshot_url)

        with closing(urllib2.urlopen(snapshot_url)) as res:
            return res.read()

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
        self.header_ended = True

    # Return: mjpeg chunk if found
    #         None: in the middle of the chunk
    def findMjpegChunk(self, line):
        if not self.boundary:   # The first time endOfChunk should be called with 'boundary' text as input
            self.boundary = line
            self.header_ended = False
            return None

        if not self.header_ended:
            if line == '\r\n':
                self.header_ended = True
            return None

        if len(line) == len(self.boundary) and line == self.boundary:  # start of next chunk
            self.header_ended = False
            return self.current_chunk.getvalue()

        self.current_chunk.write(line)
        return None
