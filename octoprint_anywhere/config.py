# coding=utf-8
from __future__ import absolute_import
import logging
import yaml

class Config:

    def __init__(self, plugin):
        from raven import Client
        self.sentry = Client('https://c6ff6cfbcc32475696753bb37c114a92:450cf825b11c4b72b901c4911878cd6c@sentry.io/1243052')

        try:
            self.config_path = plugin.get_plugin_data_folder() + "/.config.yaml"
            self._logger = logging.getLogger(__name__)
            self.load_config()
        except:
            self.sentry.captureException()
            import traceback; traceback.print_exc()

    def __getitem__(self, key):
        return self.__items__[key]

    def __setitem__(self, key, value):
        self.__items__[key] = value
        self.save_config()

    def values(self):
        return self.__items__

    def load_config(self):
        import os.path

        try:
            with open(self.config_path, 'r') as stream:
                self.__items__ = yaml.load(stream)

            if not "stream_host" in self.__items__:
                self.__items__["stream_host"] = "http://stream.getanywhere.io"
                self.save_config()

            if self.__items__["ws_host"] == "ws://getanywhere.herokuapp.com":
                self.__items__["ws_host"] = "wss://www.getanywhere.io"
                self.save_config()

        except IOError:
            self.reset_config()

    def save_config(self):
        with open(self.config_path, 'w') as outfile:
            yaml.dump(self.__items__, outfile, default_flow_style=False)

    def reset_config(self):
        try:
            import random
            import string
            # If config file not found, create a new random string as token
            token = ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits) for _ in range(32))

            with open(self.config_path, 'w') as outfile:
                self.__items__ = dict(
                        token=token,
                        registered=False,
                        ws_host="wss://www.getanywhere.io",
                        api_host="https://www.getanywhere.io",
                        stream_host="http://stream.getanywhere.io"
                        )
                yaml.dump(self.__items__, outfile, default_flow_style=False)
        except:
            self.sentry.captureException()
