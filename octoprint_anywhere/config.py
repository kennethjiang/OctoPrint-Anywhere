# coding=utf-8
from __future__ import absolute_import
import logging
import threading
import yaml
from raven import breadcrumbs
import sarge
import os

CAM_SERVER_PORT = 56720

class Config:

    def __init__(self, plugin):
        self._mutex = threading.RLock()
        self.plugin = plugin
        self.__items__ = dict()

        import raven
        self.sentry = raven.Client(
                'https://c6b6ad7ba91d48f9b8860151838327b9:76d65383ec9a4ea9b1a770dffa784dd9@sentry.getanywhere.io/1?verify_ssl=0',
                release=plugin._plugin_version
                )

        try:
            self.config_path = self.plugin.get_plugin_data_folder() + "/.config.yaml"
            self._logger = logging.getLogger(__name__)
            self.load_config()
        except:
            self.sentry.captureException()
            import traceback; traceback.print_exc()

    def __getitem__(self, key):
        with self._mutex:
            return self.__items__.get(key)

    def __setitem__(self, key, value):
        with self._mutex:
            self.__items__[key] = value
            self.save_config()

    def load_config(self):

        if not os.path.exists(self.config_path):
            self.reset_config()
            return

        try:
            with open(self.config_path, 'r') as stream:
                config_str = stream.read()

                breadcrumbs.record(message="Config file content: " + config_str)

                with self._mutex:
                    self.__items__ = yaml.load(config_str)

            if self.__items__ is None:
                raise IOError("Empty config file")

            if not "stream_host" in self.__items__:
                with self._mutex:
                    self.__items__["stream_host"] = "http://stream.getanywhere.io"
                    self.save_config()

        except IOError:
            self.sentry.captureException()
            self.reset_config()

    def save_config(self):
        with open(self.config_path, 'w') as outfile:
                with self._mutex:
                    yaml.dump(self.__items__, outfile, default_flow_style=False)

    def reset_config(self):
        original_items = self.__items__
        try:
            import random
            import string
            # If config file not found, create a new random string as token
            token = ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits) for _ in range(32))

            with open(self.config_path, 'w') as outfile:
                with self._mutex:
                    original_items.update(dict(
                            token=token,
                            registered=False,
                            ws_host="wss://www.getanywhere.io",
                            api_host="https://www.getanywhere.io",
                            stream_host="http://stream.getanywhere.io"
                            ))

                    self.__items__ = original_items
                    yaml.dump(self.__items__, outfile, default_flow_style=False)
        except:
            self.sentry.captureException()

    def set_dev_settings(self, dev_settings):
        self.dev_settings = dev_settings
        subs = dev_settings.get('subscription', [])
        sub_status = False
        if len(subs) > 0 and filter(lambda x: x['plan'] == 'premium-alpha', subs):
            sub_status = True

        if sub_status != self.__items__.get('premium_eligible'):
            self.__items__['premium_eligible'] = bool(sub_status)
            self.save_config()

    def premium_eligible(self):
        return self.__items__.get('premium_eligible', False)

    def premium_video_enabled(self):
        return self.premium_eligible() and self.__items__.get('premium_video_enabled', False)

    def enabled_premium_video(self):
        if not self.premium_eligible():
            return

        if not os.environ.get('CAM_SIM', False):
            r = sarge.run('/home/pi/oprint/bin/python -m pip install picamera', stderr=sarge.Capture())
            if not r.returncode == 0:
                raise Exception(r.stderr.text)

        save_file_path = self.plugin.get_plugin_data_folder() + "/.webcam_settings_save.yaml"
        snapshot_url_path = ['webcam', 'snapshot']
        if not os.path.exists(save_file_path):
            snapshot_url = self.plugin._settings.global_get(snapshot_url_path)
            with open(save_file_path, 'w') as outfile:
                yaml.dump({'snapshot_url': snapshot_url}, outfile, default_flow_style=False)

        self.plugin._settings.global_set(snapshot_url_path, 'http://127.0.0.1:{}/octoprint_anywhere/snapshot'.format(CAM_SERVER_PORT), force=True)
        self.plugin._settings.save(force=True)

        self.__items__['premium_video_enabled'] = True
        self.save_config()

    def disabled_premium_video(self):
        if not self.premium_eligible():
            return

        try:
            snapshot_url_path = ['webcam', 'snapshot']
            save_file_path = self.plugin.get_plugin_data_folder() + "/.webcam_settings_save.yaml"
            with open(save_file_path, 'r') as stream:
                saved = yaml.load(stream.read())
                self.plugin._settings.global_set(snapshot_url_path, saved['snapshot_url'], force=True)
                self.plugin._settings.save(force=True)

            os.remove(save_file_path)
            self.__items__['premium_video_enabled'] = False
            self.save_config()
        except:
            self.sentry.captureException()
            import traceback; traceback.print_exc()

    def get_json(self):
        import flask
        return flask.jsonify(reg_url="{0}/pub/link_printer?token={1}".format(self['api_host'], self['token']), registered=self['registered'], premium_eligible=self.premium_eligible(), premium_video_enabled=self.premium_video_enabled())
