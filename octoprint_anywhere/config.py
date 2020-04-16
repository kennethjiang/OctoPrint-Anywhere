# coding=utf-8
from __future__ import absolute_import
import logging
import threading
import yaml
from raven import breadcrumbs
import sarge
import os

class Config:

    def __init__(self, plugin):
        self._mutex = threading.RLock()
        self.plugin = plugin
        self.__items__ = dict()

        import raven
        self.sentry = raven.Client(
                'https://2b979afa37f849c1af93bcc9c88aded8:dea2054d56014d53b59376084b23e142@sentry.thespaghettidetective.com/5?verify_ssl=0',
                release=plugin._plugin_version
                )

        try:
            self.config_path = self.plugin.get_plugin_data_folder() + "/.config.yaml"
            self._logger = logging.getLogger('octoprint.plugins.anywhere')
            self.load_config()
        except:
            self.sentry.captureException()
            import traceback; traceback.print_exc()

    def __getitem__(self, key):
        with self._mutex:
            v = self.__items__.get(key)
        if key == 'stream_host' and v == 'http://stream.getanywhere.io':
            return 'http://newstream.getanywhere.io'
        else:
            return v

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
            import traceback; traceback.print_exc()
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
            import traceback; traceback.print_exc()

    def set_dev_settings(self, dev_settings):
        self.dev_settings = dev_settings

    def premium_video_eligible(self):
        return self.dev_settings.get('premium_video', False)

    def mjpeg_stream_tier(self):
        return self.dev_settings.get('mjpeg_stream_tier', 10)

    def set_picamera_error(self, error=True):
        self._picamera_error = error

    def picamera_error(self):
        return hasattr(self, '_picamera_error') and self._picamera_error


    def as_dict(self):
        return dict(reg_url="{0}/pub/link_printer?token={1}".format(self['api_host'], self['token']), registered=self['registered'])
