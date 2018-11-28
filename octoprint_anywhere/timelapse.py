# coding=utf-8
from __future__ import absolute_import
import logging
import backoff
from contextlib import closing
import threading
import requests
import os
import time

class Timelapse:

    def __init__(self):
        self._mutex = threading.RLock()
        self._should_quit = False

    def quit(self):
        with self._mutex:
            self._should_quit = True

    def should_quit(self):
        with self._mutex:
            return self._should_quit

    @backoff.on_exception(backoff.expo, Exception, max_value=6000)
    def upload_timelapses(self, stream_host, token, timelapse_dir):
        TWO_WEEKS = 60*60*24*14

        while not self.should_quit():
            r = requests.get(stream_host + "/timelapses/", headers={"Authorization": "Bearer " + token})
            r.raise_for_status()
            resp = r.json()
            if resp['device']['octolapseOptedIn']:
                all_files = [(f, os.stat(os.path.join(timelapse_dir, f))) for f in os.listdir(timelapse_dir)]
                all_files.sort(key=lambda f: f[1].st_mtime,  reverse=True) # sorted by modification timestamp

                upload_candidates = [f[0] for f in all_files if f[0].endswith(".mp4")
                        and f[1].st_mtime > (time.time() - TWO_WEEKS)][:20]   # Go back up to 2 weeks, or 20 timelapses

                uploaded_timelapses = [f['gcodeName'] for f in resp['timelapses']]
                for f in reversed(upload_candidates):
                    if not f in uploaded_timelapses:
                        time.sleep(10)  # Give the file system 10s buffer in case the file is still being written to
                        requests.post(
                            stream_host + "/timelapses/",
                            files={'file': open(os.path.join(timelapse_dir, f), 'rb')},
                            headers={"Authorization": "Bearer " + token}
                            ).raise_for_status()

            time.sleep(120)


if __name__ == "__main__":
    class ConfigStub:
        def __init__(self, path):
            self.p = path

        def load_config(self):
            import yaml
            with open(self.p, 'r') as stream:
                return yaml.load(stream)

    import logging
    logging.basicConfig()
    logging.getLogger().setLevel(logging.DEBUG)
    req_log = logging.getLogger('requests.packages.urllib3')
    req_log.setLevel(logging.DEBUG)
    req_log.propagate = True
    import sys

    upload_timelapses(ConfigStub(sys.argv[1]).load_config(), sys.argv[2])
