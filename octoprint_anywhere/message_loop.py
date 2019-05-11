# coding=utf-8
from __future__ import absolute_import

import threading
import requests
import time
import json
import os
from raven import breadcrumbs

from .mjpeg_stream import MjpegStream
from .h264_stream import H264Streamer
from .timelapse import Timelapse
from .server_ws import ServerSocket
from .remote_status import RemoteStatus
from .utils import ip_addr, ExpoBackoff, pi_version

class MessageLoop:

    def __init__(self, config, plugin):
        self._mutex = threading.RLock()
        self._should_quit = False
        self.config = config
        self.plugin = plugin

        self.remote_status = RemoteStatus()

        self.ss = None
        self.upstream = None
        self.timelapse_uploader = None
        self.op_info = None


    def quit(self):
        with self._mutex:
            self._should_quit = True

        if self.upstream:
            self.upstream.quit()
        if self.timelapse_uploader:
            self.timelapse_uploader.quit()

    def should_quit(self):
        with self._mutex:
            return self._should_quit

    def run_until_quit(self):
        try:
            stream_host = self.config['stream_host']
            token = self.config['token']

            self.upstream = MjpegStream()
            upstream_thread = threading.Thread(target=self.upstream.stream_up, args=(stream_host, token, self.plugin._printer, self.remote_status, self.plugin._settings.global_get(["webcam"]), self.config.sentry))

            if self.config.premium_video_eligible():
                if pi_version() or os.environ.get('CAM_SIM', False):
                    self.upstream = H264Streamer(stream_host, token, self.config.sentry)
                    upstream_thread = threading.Thread(target=self.upstream.start_hls_pipeline, args=(self.remote_status, self.plugin, self.config.dev_settings))
                else:
                    self.config.sentry.captureMessage('Premium video is enabled on a non-RPi platform: {}'.format(self.config['token']))

            upstream_thread.daemon = True
            upstream_thread.start()

            self.timelapse_uploader = Timelapse()
            timelapse_upload_thread = threading.Thread(target=self.timelapse_uploader.upload_timelapses, args=(stream_host, token, self.plugin._settings.settings.getBaseFolder("timelapse")))
            timelapse_upload_thread.daemon = True
            timelapse_upload_thread.start()

            self.__send_loop__()
        except:
            self.config.sentry.captureException()
            import traceback; traceback.print_exc()

    def __send_loop__(self):
        last_heartbeat = 0

        backoff = ExpoBackoff(1200)
        while not self.should_quit():
            try:
                self.ss = ServerSocket(self.config['ws_host'] + "/app/ws/device", self.config['token'], on_message=self.__on_server_ws_msg__)
                wst = threading.Thread(target=self.ss.run)
                wst.daemon = True
                wst.start()
                time.sleep(2)  # Allow the time for server ws to connect

                while self.ss.connected():
                    breadcrumbs.record(message="Message loop for: " + self.config['token'])
                    if time.time() - last_heartbeat > 60:
                        self.__send_heartbeat__()
                        last_heartbeat = time.time()

                    self.send_octoprint_data()
                    backoff.reset()
                    time.sleep(10)

            finally:
                try:
                    self.ss.disconnect()
                except:
                    pass
                backoff.more()   # When it gets here something is wrong. probably network issues. Pause before retry

    def __on_server_ws_msg__(self, ws, msg):

        def __process_job_cmd__(cmd):
            if cmd == 'pause':
                self.plugin._printer.pause_print()
            elif cmd == 'cancel':
                self.plugin._printer.cancel_print()
            elif cmd == 'resume':
                self.plugin._printer.resume_print()

        def __process_temps_cmd__(cmd):
            if 'set' in cmd:
                self.plugin._printer.set_temperature(cmd['set']['heater'], cmd['set']['target'])

        def __process_jog_cmd__(cmd):
            axis = cmd.keys()[0]
            if isinstance(cmd[axis], int):
                self.plugin._printer.jog(cmd)
            else:
                self.plugin._printer.home(axis)

        def __process_cmd__(cmd):
            for k, v in cmd.iteritems():
                if k == 'job':
                    __process_job_cmd__(v)
                if k == 'temps':
                    __process_temps_cmd__(v)
                if k == 'jog':
                    __process_jog_cmd__(v)
                elif k == 'watching':
                    self.remote_status['watching'] = v == 'True'

        msgDict = json.loads(msg)
        for k, v in msgDict.iteritems():
            if k == 'cmd':
                __process_cmd__(v)


    def send_octoprint_data(self, event_type=None, event_payload=None):
        if not self.ss:
            return

        try:
            data = self.plugin._printer.get_current_data()
            data['temps'] = self.plugin._printer.get_current_temperatures()
            data['origin'] = 'octoprint'
            if event_type:
                data['type'] = event_type
                data['payload'] = event_payload

            self.ss.send_text(json.dumps(data))
        except:
            self.config.sentry.captureException()
            import traceback; traceback.print_exc()

    def __send_heartbeat__(self):
        try:
            if not self.op_info:
                self.op_info = self.__gather_op_info__()

            self.ss.send_text(json.dumps({
                'hb': {
                    'ipAddrs': self.op_info['ip_addrs'],
                    'settings': self.op_info['settings'],
                    'octolapse': self.op_info['octolapse'],
                },
                'origin': 'oa',
                'oaVersion': self.plugin._plugin_version
            }, encoding='latin1'))
        except:
            self.config.sentry.captureException()
            import traceback; traceback.print_exc()

    def __gather_op_info__(self):
        octolapse = self.plugin._plugin_manager.get_plugin_info('octolapse')
        return {
                'ip_addrs': ip_addr(),
                'octolapse': {'version': octolapse.version, 'enabled': octolapse.enabled} if octolapse else None,
                'settings': {
                        'temperature': self.plugin._settings.settings.effective['temperature']
                    }
                }

