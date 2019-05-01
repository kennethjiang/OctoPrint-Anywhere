import io
import subprocess
from collections import deque
from threading import Thread
import picamera
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import requests

kkk = 0
class TSWatcher(FileSystemEventHandler):

    def __init__(self, ts_q):
        super(TSWatcher, self).__init__()
        self.ts_q = ts_q

    def on_created(self, event):
        m3u8 = list(self.ts_q)
        if len(m3u8) < 10:
            return

        files = {'file': ('ts', open('/tmp/oa-ts/'+m3u8[len(m3u8)-1].strip(), 'rb'))}
        resp = requests.post('http://192.168.0.185:3000/pub/video_ts', data={'m3u8': m3u8[-2:]}, files=files)


ts_q = deque([], 24)
def start_hls_pipeline():

    global ts_q

    event_handler = TSWatcher(ts_q)
    observer = Observer()
    observer.schedule(event_handler, '/tmp/oa-ts')
    observer.start()

    sub_proc = subprocess.Popen('/home/pi/ffmpeg/ffmpeg -re -i pipe:0 -y -an -vcodec copy -f hls -hls_time 2 -hls_list_size 10 -hls_delete_threshold 10 -hls_flags split_by_time+delete_segments+second_level_segment_index -strftime 1 -hls_segment_filename /tmp/oa-ts/%s-%%d.ts -hls_segment_type mpegts -'.split(' '), stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    camera = picamera.PiCamera(framerate=25)
    camera.resolution = (640, 480)
    import threading
    x = threading.Thread(target=exhaust_m3u8, args=(sub_proc, ts_q))
    x.setDaemon(True)
    x.start()
    camera.start_recording(sub_proc.stdin, format='h264', quality=23)
    #exhaust_m3u8(sub_proc, ts_q)
    while True:
        camera.wait_recording(2)
        #camera.stop_recording()
        import time
        #time.sleep(4)

def exhaust_m3u8(sub_proc, ts_q):
    while True:
        ts_q.append(sub_proc.stdout.readline())
    

from flask import Flask, request, Response, send_from_directory
app = Flask(__name__)

@app.route('/<path:path>')
def send_js(path):
    return send_from_directory('/tmp/oa-ts', path)


def start_server():
    app.run(host='0.0.0.0', port=3333, threaded=False)

@app.route('/livestream.m3u8')
def livestream_m3u8():
    global start
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
start_hls_pipeline()
