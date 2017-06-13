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

import logging
import os
from threading import Thread
from Queue import Queue
import backoff

from .mjpeg_stream import capture_mjpeg
from .octoprint_ws import listen_to_octoprint
from .server_ws import ServerSocket

class AnywherePlugin(octoprint.plugin.SettingsPlugin,
                     octoprint.plugin.AssetPlugin,
                     octoprint.plugin.TemplatePlugin,
                     octoprint.plugin.StartupPlugin,):

    ##~~ AssetPlugin mixin
    def get_assets(self):
        return dict(
                js=["js/anywhere.js"]
                )

    ##~~ SettingsPlugin mixin
    def get_settings_defaults(self):
        pass

    def on_settings_save(self, data):
        pass

    def get_update_information(self):
        # Define the configuration for your plugin to use with the Software Update
        # Plugin here. See https://github.com/foosel/OctoPrint/wiki/Plugin:-Software-Update
        # for details.
        return dict(
            anywhere=dict(
                displayName="OctoPrint Anywhere",
                displayVersion=self._plugin_version,

                # version check: github repository
                type="github_release",
                user="kennethjiang",
                repo="OctoPrint-Anywhere",
                current=self._plugin_version,

                # update method: pip
                pip="https://github.com/kennethjiang/OctoPrint-Anywhere/archive/{target_version}.zip"
            )
        )

    def get_template_configs(self):
        return [ dict(type="settings", template="anywhere_settings.jinja2", custom_bindings=True) ]

    def get_template_vars(self):
        self.__load_config()
        return self.config

    def on_after_startup(self):
        self._logger = logging.getLogger(__name__)

        import tornado.autoreload
        tornado.autoreload.start()
        for dir, _, files in os.walk(self._basefolder):
            [tornado.autoreload.watch(dir + '/' + f) for f in files if not f.startswith('.')]

        self.__load_config()

        self.__start_mjpeg_capture__()

        self.message_q = Queue()
        # listen to OctoPrint websocket in another thread
        listen_to_octoprint(self._settings.settings, self.message_q)

        main_thread = Thread(target=self.__message_loop__)
        main_thread.daemon = True
        main_thread.start()

    def __load_config(self):
        CONFIG_PATH= self._basefolder + "/.config.yaml"
        try:
            import yaml
            with open(CONFIG_PATH, 'r') as stream:
                self.config = yaml.load(stream)
        except IOError:
            import random
            import string
            # If config file not found, create a new random string as token
            token = ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits) for _ in range(32))

            with open(CONFIG_PATH, 'w') as outfile:
                c = dict(token=token, registered=False)
                yaml.dump(c, outfile, default_flow_style=False)
                self.config = c

    @backoff.on_exception(backoff.expo, Exception, max_value=240)
    @backoff.on_predicate(backoff.expo, max_value=240)
    def __message_loop__(self):

        @backoff.on_exception(backoff.fibo, Exception, max_tries=8)
        @backoff.on_predicate(backoff.fibo, max_tries=8)
        def __forward_ws__(ss, message_q, webcam_q):
            while ss.connected():
                while not message_q.empty():
                    ss.send_text(message_q.get_nowait())

                last_chunk = None
                while not webcam_q.empty():  # Get the last chunk and empty the queue
                    last_chunk = webcam_q.get_nowait()
                if last_chunk:
                    ss.send_binary(last_chunk)
                    import time
                    time.sleep(30)

        self.__connect_server_ws__()
        __forward_ws__(self.ss, self.message_q, self.webcam_q)
        self._logger.warn("Time out in waiting for server ws connection")
        try:
            self.ss.close()
        except:
            pass

    def __connect_server_ws__(self):
        self.ss = ServerSocket("ws://10.0.2.2:6001/app/ws/device", "1234")
        #self.ss = ServerSocket("ws://getanywhere-stg.herokuapp.com/app/ws", "1234")
        wst = Thread(target=self.ss.run)
        wst.daemon = True
        wst.start()

    def __start_mjpeg_capture__(self):
        self.webcam = self._settings.global_get(["webcam"])

        if self.webcam:
            self.webcam_q = Queue()
            producer = Thread(target=capture_mjpeg, args=(self.webcam_q, self.webcam["stream"]))
            producer.daemon = True
            producer.start()

# If you want your plugin to be registered within OctoPrint under a different name than what you defined in setup.py
# ("OctoPrint-PluginSkeleton"), you may define that here. Same goes for the other metadata derived from setup.py that
# can be overwritten via __plugin_xyz__ control properties. See the documentation for that.
__plugin_name__ = "OctoPrint Anywhere"

def __plugin_load__():
    global __plugin_implementation__
    __plugin_implementation__ = AnywherePlugin()

    global __plugin_hooks__
    __plugin_hooks__ = {
        "octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information
    }

