# coding=utf-8
from __future__ import absolute_import
import logging
import yaml

class Config:

    def __init__(self, plugin):
        self.config_path = plugin.get_plugin_data_folder() + "/.config.yaml"
        self.old_config_path = plugin._basefolder + "/.config.yaml"
        self._logger = logging.getLogger(__name__)
        self.load_config()

    def __getitem__(self, key):
        return self.__items__[key]

    def __setitem__(self, key, value):
        self.__items__[key] = value
        self.save_config()

    def values(self):
        return self.__items__

    def load_config(self):
        import os.path
        if os.path.isfile(self.old_config_path):
            try:
                import shutil
                shutil.move(self.old_config_path, self.config_path)
            except Exception as ex:
                self._logger.exception(ex)

        try:
            with open(self.config_path, 'r') as stream:
                self.__items__ = yaml.load(stream)
        except IOError:
            self.reset_config()

    def save_config(self):
        with open(self.config_path, 'w') as outfile:
            yaml.dump(self.__items__, outfile, default_flow_style=False)

    def reset_config(self):
        import random
        import string
        # If config file not found, create a new random string as token
        token = ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits) for _ in range(32))

        with open(self.config_path, 'w') as outfile:
            self.__items__ = dict(
                    token=token,
                    registered=False,
                    ws_host="ws://getanywhere.herokuapp.com",
                    api_host="https://www.getanywhere.io"
                    )
            yaml.dump(self.__items__, outfile, default_flow_style=False)
