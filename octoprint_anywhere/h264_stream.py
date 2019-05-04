import io
import os
import subprocess
import time
import flask
from collections import deque
from threading import Thread
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import requests

from .utils import pi_version

CAM_SERVER_PORT = 56720
FFMPEG = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'bin', 'ffmpeg')

TS_TEMP_DIR = '/tmp/octoprintanywhere-ts'
if not os.path.exists(TS_TEMP_DIR):
    os.mkdir(TS_TEMP_DIR)

class WebcamServer:
    def __init__(self, camera):
        self.camera = camera

    def capture_image(self):
        output = io.BytesIO()
        self.camera.capture(output, format='jpeg')
        return output

    def mjpeg_generator(self, boundary):
      try:
        hdr = '--%s\r\nContent-Type: image/jpeg\r\n' % boundary
        bio = io.BytesIO()

        prefix = ''
        for foo in self.camera.capture_continuous(bio, format='jpeg', use_video_port=True):
            msg = prefix + hdr + 'Content-Length: %d\r\n\r\n'.format(bio.tell())
            bio.seek(0)
            yield msg.encode('utf-8') + bio.read()
            bio.seek(0)
            bio.truncate()
            prefix = '\r\n'
      except GeneratorExit:
         print('closed')

    def run_forever(self):
        webcam_server_app = flask.Flask('webcam_server')

        @webcam_server_app.route('/octoprint_anywhere/snapshot')
        def get_snapshot():
            output = self.capture_image()
            output.seek(0)
            return flask.send_file(output, mimetype='image/jpg')

        @webcam_server_app.route('/octoprint_anywhere/mjpeg')
        def get_mjpeg():
            boundary='herebedragons'
            return flask.Response(flask.stream_with_context(self.mjpeg_generator(boundary)), mimetype='multipart/x-mixed-replace;boundary=%s' % boundary)

        webcam_server_app.run(host='0.0.0.0', port=CAM_SERVER_PORT, threaded=True)

    def start(self):
        cam_server_thread = Thread(target=self.run_forever)
        cam_server_thread.daemon = True
        cam_server_thread.start()


class TSWatcher(FileSystemEventHandler):

    def __init__(self, stream_host, token, m3u8_q):
        super(TSWatcher, self).__init__()
        self.stream_host = stream_host
        self.m3u8_q = m3u8_q
        self.token = token

    def on_created(self, event):
        m3u8 = list(self.m3u8_q)
        if len(m3u8) < 10:
            return

        try:
            files = {'file': ('ts', open(os.path.join(TS_TEMP_DIR, m3u8[len(m3u8)-1].strip()), 'rb'))}
            requests.post(self.stream_host+'/video/mpegts', data={'m3u8': m3u8[-2:]}, files=files, headers={"Authorization": "Bearer " + self.token}).raise_for_status()
        except:
            import sys, traceback
            traceback.print_exc(file=sys.stdout)


class H264Streamer:

    def __init__(self):
        self.m3u8_q = deque([], 24)

        if not pi_version():
            self.camera = StubCamera()
            global FFMPEG
            FFMPEG = 'ffmpeg'
        else:
            import picamera
            self.camera = picamera.PiCamera(framerate=25, resolution=(640, 480))

        self.camera.start_preview()

    def start_hls_pipeline(self, stream_host, token, remote_status):

        self.webcam_server = WebcamServer(self.camera)
        self.webcam_server.start()

        event_handler = TSWatcher(stream_host, token, self.m3u8_q)
        observer = Observer()
        observer.schedule(event_handler, TS_TEMP_DIR)
        observer.start()

        sub_proc = subprocess.Popen('{} -re -i pipe:0 -y -an -vcodec copy -f hls -hls_time 2 -hls_list_size 10 -hls_delete_threshold 10 -hls_flags split_by_time+delete_segments+second_level_segment_index -strftime 1 -hls_segment_filename {}/%s-%%d.ts -hls_segment_type mpegts -'.format(FFMPEG, TS_TEMP_DIR).split(' '), stdin=subprocess.PIPE, stdout=subprocess.PIPE)

        x = Thread(target=self.exhaust_m3u8, args=(sub_proc,))
        x.setDaemon(True)
        x.start()
        #exhaust_m3u8(sub_proc, m3u8_q)

        while True:
            if remote_status['watching']:
                self.camera.start_recording(sub_proc.stdin, format='h264', quality=23)
                while remote_status['watching']:
                    self.camera.wait_recording(2)
                self.camera.stop_recording()
                self.camera.start_preview()
            else:
                time.sleep(0.5)


    def exhaust_m3u8(self, sub_proc):
        while True:
            self.m3u8_q.append(sub_proc.stdout.readline())


class StubCamera:

    def __init__(self):
        from itertools import cycle
        h264s_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'h264s')
        h264s = map(lambda x: os.path.join(h264s_path, x), sorted(os.listdir(h264s_path)))
        self.h264_files = cycle(h264s)
        self.running = False

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

            with open(fn) as f:
                stream.write(f.read())
                time.sleep(0.04)


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
