# coding=utf-8
from __future__ import absolute_import

### (Don't forget to remove me)
# This is a basic skeleton for your plugin's __init__.py. You probably want to adjust the class name of your plugin
# as well as the plugin mixins it's subclassing from. This is really just a basic skeleton to get you started,
# defining your plugin as a template plugin, settings and asset plugin. Feel free to add or remove mixins
# as necessary.
#
# Take a look at the documentation on what other plugin mixins are available.

import octoprint.plugin

import os
from threading import Thread
from Queue import Queue

from .mjpeg_stream import capture_mjpeg

class RemoteControlPlugin(octoprint.plugin.SettingsPlugin,
        octoprint.plugin.StartupPlugin,):

    ##~~ SettingsPlugin mixin

    def get_settings_defaults(self):
        return dict(
            # put your plugin's default settings here
        )

    def on_settings_save(self, data):
        old_flag = self._settings.get_boolean(["sub", "some_flag"])

    def get_update_information(self):
        # Define the configuration for your plugin to use with the Software Update
        # Plugin here. See https://github.com/foosel/OctoPrint/wiki/Plugin:-Software-Update
        # for details.
        return dict(
            slicer=dict(
                displayName="Remote Control",
                displayVersion=self._plugin_version,

                # version check: github repository
                type="github_release",
                user="kennethjiang",
                repo="OctoPrint-RemoteControl",
                current=self._plugin_version,

                # update method: pip
                pip="https://github.com/kennethjiang/OctoPrint-RemoteControl/archive/{target_version}.zip"
            )
        )

    def on_after_startup(self):
        import tornado.autoreload
        tornado.autoreload.start()
        for dir, _, files in os.walk(self._basefolder):
            [tornado.autoreload.watch(dir + '/' + f) for f in files if not f.startswith('.')]

        self.__connect__()

    def __connect__(self):
        self.__start_mjpeg_capture__()

    def __start_mjpeg_capture__(self):
        self.webcam = self._settings.global_get(["webcam"])

        if self.webcam:
            self.q = Queue()
            producer = Thread(target=capture_mjpeg, args=(self.q, self.webcam["stream"]))
            producer.start()


# If you want your plugin to be registered within OctoPrint under a different name than what you defined in setup.py
# ("OctoPrint-PluginSkeleton"), you may define that here. Same goes for the other metadata derived from setup.py that
# can be overwritten via __plugin_xyz__ control properties. See the documentation for that.
__plugin_name__ = "RemoteControl"

def __plugin_load__():
    global __plugin_implementation__
    __plugin_implementation__ = RemoteControlPlugin()

    global __plugin_hooks__
    __plugin_hooks__ = {
        "octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information
    }

