import io
import subprocess
import time
from collections import deque
from threading import Thread
import picamera
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import requests

class TSWatcher(FileSystemEventHandler):

    def __init__(self, token, ts_q):
        super(TSWatcher, self).__init__()
        self.ts_q = ts_q
        self.token = token

    def on_created(self, event):
        m3u8 = list(self.ts_q)
        if len(m3u8) < 10:
            return

        try:
            files = {'file': ('ts', open('/tmp/oa-ts/'+m3u8[len(m3u8)-1].strip(), 'rb'))}
            requests.post('http://192.168.0.185:3000/video/mpegts', data={'m3u8': m3u8[-2:]}, files=files, headers={"Authorization": "Bearer " + self.token}).raise_for_status()
        except:
            import sys, traceback
            traceback.print_exc(file=sys.stdout)


class H264Streamer:

    def __init__(self):
        self.ts_q = deque([], 24)

    def start_hls_pipeline(self, token, remote_status):
        camera = picamera.PiCamera(framerate=25)
        camera.resolution = (640, 480)

        event_handler = TSWatcher(token, self.ts_q)
        observer = Observer()
        observer.schedule(event_handler, '/tmp/oa-ts')
        observer.start()

        sub_proc = subprocess.Popen('/home/pi/ffmpeg/ffmpeg -re -i pipe:0 -y -an -vcodec copy -f hls -hls_time 2 -hls_list_size 10 -hls_delete_threshold 10 -hls_flags split_by_time+delete_segments+second_level_segment_index -strftime 1 -hls_segment_filename /tmp/oa-ts/%s-%%d.ts -hls_segment_type mpegts -'.split(' '), stdin=subprocess.PIPE, stdout=subprocess.PIPE)

        x = Thread(target=self.exhaust_m3u8, args=(sub_proc,))
        x.setDaemon(True)
        x.start()
        #exhaust_m3u8(sub_proc, ts_q)

        camera.start_preview()
        while True:
            if remote_status['watching']:
                camera.start_recording(sub_proc.stdin, format='h264', quality=23)
                while remote_status['watching']:
                    camera.wait_recording(2)
                camera.stop_recording()
                camera.start_preview()
            else:
                time.sleep(0.5)


    def exhaust_m3u8(self, sub_proc):
        while True:
            self.ts_q.append(sub_proc.stdout.readline())
    

if __name__ == "__main__":

    from flask import Flask, request, Response, send_from_directory
    app = Flask(__name__)

    @app.route('/<path:path>')
    def send_js(path):
        return send_from_directory('/tmp/oa-ts', path)


    def start_server():
        app.run(host='0.0.0.0', port=3333, threaded=False)

    @app.route('/livestream.m3u8')
    def livestream_m3u8():
        response = '\n'.join(list(ts_q))
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
