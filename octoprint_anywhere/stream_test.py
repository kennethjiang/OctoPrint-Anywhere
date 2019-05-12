import io
import os
import logging
import subprocess
import time
import flask
from collections import deque
import Queue
from threading import Thread, RLock
import requests
import yaml
import sys

_logger = logging.getLogger(__name__)

FFMPEG = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bin', 'ffmpeg')

TS_TEMP_DIR = '/tmp/octoprintanywhere-ts'
if not os.path.exists(TS_TEMP_DIR):
    os.mkdir(TS_TEMP_DIR)


class H264Streamer:

    def __init__(self, stream_host, token, sentryClient):
        self.m3u8_q = deque([], 24)
        self.stream_host = stream_host
        self.token = token

    def __init_camera__(self, plugin, dev_settings):

            import picamera
            self.camera = picamera.PiCamera()
	    self.camera.framerate=25
	    self.camera.resolution=(640, 480)

            self.camera.start_preview()

    def start_hls_pipeline(self, remote_status, plugin, dev_settings):
        self.__init_camera__(plugin, dev_settings)

        # Stream timestamps should be reset when ffmepg restarts
        requests.delete(self.stream_host+'/video/mpegts')

        ffmpeg_cmd = '{} -re -i pipe:0 -y -an -vcodec copy -f hls -hls_time 2 -hls_list_size 10 -hls_delete_threshold 10 -hls_flags split_by_time+delete_segments+second_level_segment_index -strftime 1 -hls_segment_filename {}/%s-%%d.ts -hls_segment_type mpegts -'.format(FFMPEG, TS_TEMP_DIR)
        _logger.info('Launching: ' + ffmpeg_cmd)
        sub_proc = subprocess.Popen(ffmpeg_cmd.split(' '), stdin=subprocess.PIPE, stdout=subprocess.PIPE)

        self.camera.start_recording(sub_proc.stdin, format='h264', quality=23)
        self.poll_m3u8(sub_proc)

    def poll_m3u8(self, sub_proc):
        last_10 = deque([], 10)
        while True:
            l = sub_proc.stdout.readline().strip()
            if l.endswith('.ts') and not l in last_10:
                last_10.append(l)
                self.upload_mpegts_to_server(os.path.join(TS_TEMP_DIR,l))

    def upload_mpegts_to_server(self, mpegts):
            files = {'file': ('ts', open(mpegts), 'rb')}
            r = requests.post(self.stream_host+'/video/mpegts', data={'filename': mpegts}, files=files)
            r.raise_for_status()


if __name__ == "__main__":

    if len(sys.argv) > 1:
        H264Streamer(sys.argv[1], None, None).start_hls_pipeline(None, None, None)

    from flask import Flask, request, Response, send_from_directory
    app = Flask(__name__)
    app.DEBUG = True

    @app.route('/<path:path>')
    def send_js(path):
        import random
        time.sleep(random.randrange(10)/2.0)
        return send_from_directory(TS_TEMP_DIR, path)

    def start_server():
        app.run(host='0.0.0.0', port=3333, threaded=True)

    @app.route('/livestream.m3u8')
    def livestream_m3u8():
        response = '\n'.join(list(m3u8_q))
        resp = Response(response, mimetype='application/vnd.apple.mpegurl')
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Methods"] = "POST, GET, OPTIONS"
        resp.headers["Access-Control-Max-Age"] = "1000"
        resp.headers["Access-Control-Allow-Headers"] = "*"

        return resp

    ffmpeg_cmd = '{} -re -i pipe:0 -y -an -vcodec copy -f hls -hls_time 10 -hls_list_size 10 -hls_delete_threshold 10 -hls_flags split_by_time+delete_segments+second_level_segment_index -strftime 1 -hls_segment_filename {}/%s-%%d.ts -hls_segment_type mpegts {}'.format(FFMPEG, TS_TEMP_DIR, os.path.join(TS_TEMP_DIR, 'stream.m3u8'))
    _logger.info('Launching: ' + ffmpeg_cmd)
    sub_proc = subprocess.Popen(ffmpeg_cmd.split(' '), stdin=subprocess.PIPE)

    import picamera
    camera = picamera.PiCamera()
    camera.framerate=25
    camera.resolution=(640, 480)
    camera.start_recording(sub_proc.stdin, format='h264', quality=23)
    start_server()
