import io
import subprocess
from collections import deque
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
        resp = requests.post('http://192.168.0.185:3000/pub/video_ts', data={'m3u8': m3u8}, files=files)

def start_hls_pipeline():

    ts_q = deque([], 12)

    event_handler = TSWatcher(ts_q)
    observer = Observer()
    observer.schedule(event_handler, '/tmp/oa-ts')
    observer.start()

    sub_proc = subprocess.Popen('/home/pi/ffmpeg/ffmpeg -re -i pipe:0 -y -an -vcodec copy -f hls -hls_time 1 -hls_list_size 10 -hls_delete_threshold 10 -hls_flags split_by_time+delete_segments+second_level_segment_index -strftime 1 -hls_segment_filename /tmp/oa-ts/%s-%%d.ts -hls_segment_type mpegts -'.split(' '), stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    camera = picamera.PiCamera()
    camera.resolution = (640, 480)
    import threading
    x = threading.Thread(target=exhaust_m3u8, args=(sub_proc, ts_q))
    x.setDaemon(True)
    x.start()
    while True:
        camera.start_recording(sub_proc.stdin, format='h264', quality=23)
        camera.wait_recording(1)
        camera.stop_recording()
        import time
        #time.sleep(4)

def exhaust_m3u8(sub_proc, ts_q):
    while True:
        ts_q.append(sub_proc.stdout.readline())
    

start_hls_pipeline()
