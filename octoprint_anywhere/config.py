# coding=utf-8
from __future__ import absolute_import
import logging
import yaml

class Config(dict):

    def __init__(self, plugin):
        self.config_path = plugin.get_plugin_data_folder() + "/.config.yaml"
        self.old_config_path = plugin._basefolder + "/.config.yaml"
        self._logger = logging.getLogger(__name__)

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
                return yaml.load(stream)
        except IOError:
            return None
