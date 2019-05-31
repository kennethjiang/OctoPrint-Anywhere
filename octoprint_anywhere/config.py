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

    def premium_video_eligible(self):
        return self.dev_settings.get('premium_video', False)

    def as_dict(self):
        return dict(reg_url="{0}/pub/link_printer?token={1}".format(self['api_host'], self['token']), registered=self['registered'])
