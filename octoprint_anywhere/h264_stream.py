import io
import os
import logging
import subprocess
import time
import sarge
import flask
from collections import deque
from threading import Thread, RLock, Condition
import requests
import yaml
from raven import breadcrumbs
import sys

from .utils import pi_version

_logger = logging.getLogger(__name__)

FFMPEG = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bin', 'ffmpeg')

TS_TEMP_DIR = '/tmp/octoprintanywhere-ts'
if not os.path.exists(TS_TEMP_DIR):
    os.mkdir(TS_TEMP_DIR)

class WebcamServer:
    def __init__(self, camera):
        self.camera = camera
        self._frame = None
        self._frame_lock = Condition()
        self._frame_requests = 0
        self._frame_requested_lock = Condition()

    def capture_forever(self):

        bio = io.BytesIO()
        for foo in self.camera.capture_continuous(bio, format='jpeg'):
            bio.seek(0)
            chunk = bio.read()
            bio.seek(0)
            bio.truncate()

            with self._frame_lock:
                self._frame = chunk
                self._frame_lock.notify_all()

                ts_wait_start = time.time()
                while self._frame:
                    self._frame_lock.wait(5.0)

                    if time.time() - ts_wait_start > 5.0:  # Have waited for more than 5s for consumer thread to consume frame. Some consumer threads have erred out
                        with self._frame_requested_lock:
                            self._frame_requests = 0
                            self._frame = None

            with self._frame_requested_lock:
                while self._frame_requests <= 0:   # Wait for the next request to come in
                    self._frame_requested_lock.wait()
            self.ts = time.time()

    def get_frame(self):
        with self._frame_requested_lock:
            self._frame_requests += 1
            self._frame_requested_lock.notify_all()

        with self._frame_lock:
            while not self._frame:
                self._frame_lock.wait(5.0)

            frame = self._frame

        with self._frame_requested_lock:
            self._frame_requests -= 1

            if self._frame_requests <= 0:
                self._frame_requests = 0

                with self._frame_lock:
                    self._frame = None
                    self._frame_lock.notify_all()

        return frame

    def mjpeg_generator(self, boundary):
      try:
        hdr = '--%s\r\nContent-Type: image/jpeg\r\n' % boundary

        prefix = ''
        while True:
            chunk = self.get_frame()
            msg = prefix + hdr + 'Content-Length: {}\r\n\r\n'.format(len(chunk))
            yield msg.encode('utf-8') + chunk
            time.sleep(0.2)
            prefix = '\r\n'
      except GeneratorExit:
         pass

    def get_snapshot(self):
        return flask.send_file(io.BytesIO(self.get_frame()), mimetype='image/jpeg')

    def get_mjpeg(self):
        boundary='herebedragons'
        return flask.Response(flask.stream_with_context(self.mjpeg_generator(boundary)), mimetype='multipart/x-mixed-replace;boundary=%s' % boundary)

    def run_forever(self):
        webcam_server_app = flask.Flask('webcam_server')

        @webcam_server_app.route('/')
        def webcam():
            action = flask.request.args['action']
            if action == 'snapshot':
                return self.get_snapshot()
            else:
                return self.get_mjpeg()

        webcam_server_app.run(host='0.0.0.0', port=8080, threaded=True)

    def start(self):
        cam_server_thread = Thread(target=self.run_forever)
        cam_server_thread.daemon = True
        cam_server_thread.start()

        capture_thread = Thread(target=self.capture_forever)
        capture_thread.daemon = True
        capture_thread.start()


class H264Streamer:

    def __init__(self, stream_host, token, sentryClient):
        self.m3u8_q = deque([], 24)
        self.stream_host = stream_host
        self.token = token
        self.sentryClient = sentryClient

    def __init_camera__(self, plugin, dev_settings):

        def resolution_tuple(dev_settings):
            res_map = {
                    "low": (320,240),
                    "medium": (640, 480),
                    "high": (1296, 972),
                    "high_16_9": (1280, 720),
                    "ultrahigh_16_9": (1920, 1080),
                    }
            resolution = res_map[dev_settings.get('camResolution', 'medium')]

            return reversed(resolution) if dev_settings.get('rotate90', False) ^ dev_settings.get('rotate90N', False) else resolution   # need to swap width and height if rotated

        if not pi_version():
            self.camera = StubCamera()
            global FFMPEG
            FFMPEG = 'ffmpeg'
        else:
            sarge.run('sudo service webcamd stop')

            try:
                import picamera
                self.camera = picamera.PiCamera()
	        self.camera.framerate=25
	        self.camera.resolution=resolution_tuple(dev_settings)
	        self.camera.hflip=dev_settings.get('flipH', False)
	        self.camera.vflip=dev_settings.get('flipV', False)

                rotation = (90 if dev_settings.get('rotate90', False) else 0)
                rotation += (-90 if dev_settings.get('rotate90N', False) else 0)
	        self.camera.rotation=rotation

                self.camera.start_preview()
            except:
	        arge.run('sudo service webcamd start')   # failed to start picamera. falling back to mjpeg-streamer
                plugin.picamera_error = True
                self.sentryClient.captureException()
                import traceback; traceback.print_exc()
                return False
        return True

    def start_hls_pipeline(self, remote_status, plugin, dev_settings):
        if not self.__init_camera__(plugin, dev_settings):
            return

        self.webcam_server = WebcamServer(self.camera)
        self.webcam_server.start()

        # Stream timestamps should be reset when ffmepg restarts
        requests.delete(self.stream_host+'/video/mpegts', headers={"Authorization": "Bearer " + self.token})

        ffmpeg_cmd = '{} -re -i pipe:0 -y -an -vcodec copy -f hls -hls_time 2 -hls_list_size 10 -hls_delete_threshold 10 -hls_flags split_by_time+delete_segments+second_level_segment_index -strftime 1 -hls_segment_filename {}/%s-%%d.ts -hls_segment_type mpegts -'.format(FFMPEG, TS_TEMP_DIR)
        _logger.info('Launching: ' + ffmpeg_cmd)
        sub_proc = subprocess.Popen(ffmpeg_cmd.split(' '), stdin=subprocess.PIPE, stdout=subprocess.PIPE)

        m3u8_thread = Thread(target=self.poll_m3u8, args=(sub_proc,))
        m3u8_thread.setDaemon(True)
        m3u8_thread.start()

        while True:
            if remote_status['watching']:
                self.camera.start_recording(sub_proc.stdin, format='h264', quality=(30 if 'high' in dev_settings.get('camResolution', 'medium') else 23))
                while remote_status['watching']:
                    self.camera.wait_recording(2)
                self.camera.wait_recording(4)   # record 4 more seconds to minimize the pause user views the stream again
                self.camera.stop_recording()
                self.camera.start_preview()
            else:
                time.sleep(0.05)

    def poll_m3u8(self, sub_proc):
        last_10 = deque([], 10)
        while True:
            l = sub_proc.stdout.readline().strip()
            if l.endswith('.ts') and not l in last_10:
                last_10.append(l)
                self.upload_mpegts_to_server(os.path.join(TS_TEMP_DIR,l))

    def upload_mpegts_to_server(self, mpegts):
        try:
            breadcrumbs.record(message="Token to upload mpegts: " + self.token)
            files = {'file': ('ts', open(mpegts), 'rb')}
            r = requests.post(self.stream_host+'/video/mpegts', data={'filename': mpegts}, files=files, headers={"Authorization": "Bearer " + self.token})
            r.raise_for_status()
        except:
            self.sentryClient.captureException()
            import traceback; traceback.print_exc()


class StubCamera:

    def __init__(self):
        from itertools import cycle
        h264s_path = '/mjpg-streamer/h264s'
        h264s = map(lambda x: os.path.join(h264s_path, x), sorted(os.listdir(h264s_path)))
        self.h264_files = cycle(h264s)
        self.running = False
        self.last_frame = 0

    def capture_continuous(self, bio, format='jpeg', use_video_port=True):
        return []

    def start_preview(self):
        pass

    def start_recording(self, stream, **kargs):
        self.running = True
        thr = Thread(target=self.stream_h264_files, args=(stream,))
        thr.setDaemon(True)
        thr.start()

    def stop_recording(self):
        self.running = False

    def wait_recording(self, seconds):
        time.sleep(seconds)

    def stream_h264_files(self, stream):
        for fn in self.h264_files:
            if not self.running:
                return

            time.sleep(max(2 - (time.time() - self.last_frame), 0))
            self.last_frame = time.time()
            with open(fn) as f:
                stream.write(f.read())


if __name__ == "__main__":

    from flask import Flask, request, Response, send_from_directory
    app = Flask(__name__)

    @app.route('/<path:path>')
    def send_js(path):
        return send_from_directory(TS_TEMP_DIR, path)


    def start_server():
        app.run(host='0.0.0.0', port=3333, threaded=False)

    @app.route('/livestream.m3u8')
    def livestream_m3u8():
        response = '\n'.join(list(m3u8_q))
        resp = Response(response, mimetype='application/vnd.apple.mpegurl')
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Methods"] = "POST, GET, OPTIONS"
        resp.headers["Access-Control-Max-Age"] = "1000"
        resp.headers["Access-Control-Allow-Headers"] = "*"

        return resp

    t2 = Thread(target=start_server)
    t2.daemon = True
    t2.start()
    H264Streamer().start_hls_pipeline('asdf', {'watching': True})
