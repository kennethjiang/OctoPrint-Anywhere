# coding=utf-8
from __future__ import absolute_import

import octoprint.plugin
import json

import logging
import os
import threading
from Queue import Queue
import backoff
import requests
from ratelimit import rate_limited

from .mjpeg_stream import capture_mjpeg, stream_up
from .octoprint_ws import listen_to_octoprint
from .server_ws import ServerSocket
from .config import Config

class AnywherePlugin(octoprint.plugin.SettingsPlugin,
                     octoprint.plugin.AssetPlugin,
                     octoprint.plugin.TemplatePlugin,
                     octoprint.plugin.StartupPlugin,
                     octoprint.plugin.WizardPlugin,):

    ##~~ AssetPlugin mixin
    def get_assets(self):
        return dict(
                js=["js/anywhere.js"]
                )

    ##########
    ### Wizard API
    ##########

    def is_wizard_required(self):
        self.config = Config(self).load_config()
        return not self.config['registered']

    def get_wizard_version(self):
        return 2
        # Wizard version numbers used in releases
        # < 1.4.2 : no wizard
        # 1.4.2 : 1
        # 1.4.3 : 1

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
        self.config = Config(self).load_config()
        return self.config

    def on_after_startup(self):
        self._logger = logging.getLogger(__name__)

        self.message_q = Queue(maxsize=128)

        main_thread = threading.Thread(target=self.__message_loop__)
        main_thread.daemon = True
        main_thread.start()

        self.__start_mjpeg_capture__()

        # listen to OctoPrint websocket in another thread
        listen_to_octoprint(self._settings.settings, self.message_q)

    @backoff.on_exception(backoff.expo, Exception, max_value=240)
    @backoff.on_predicate(backoff.expo, max_value=240)
    def __message_loop__(self):

        @backoff.on_exception(backoff.fibo, Exception, max_tries=8)
        @backoff.on_predicate(backoff.fibo, max_tries=8)
        def __forward_ws__(ss, message_q):

            @rate_limited(period=1, every=4.0)
            def __exhaust_message_queues__(ss, message_q):
                while not message_q.empty():
                    ss.send_text(message_q.get_nowait())

            while ss.connected():
                __exhaust_message_queues__(ss, message_q)
            self._logger.warn("Not connected to server ws or connection lost")

        self.config = Config(self).load_config()

        if (not self.config['registered']):
            self.__probe_auth_token__()  # Forever loop to probe if token is registered with server
            self.config['registered'] = True
            Config(self).save_config(self.config)

        self.__connect_server_ws__()
        __forward_ws__(self.ss, self.message_q)
        self._logger.warn("Reached max backoff in waiting for server ws connection")
        try:
            self.ss.close()
        except:
            pass

    def __connect_server_ws__(self):
        self.ss = ServerSocket(self.config['ws_host'] + "/app/ws/device", self.config['token'], on_message=self.__on_server_ws_msg__)
        wst = threading.Thread(target=self.ss.run)
        wst.daemon = True
        wst.start()

    def __on_server_ws_msg__(self, ws, msg):

        def __process_job_cmd__(cmd):
            if cmd == 'pause':
                self._printer.pause_print()
            elif cmd == 'cancel':
                self._printer.cancel_print()
            elif cmd == 'resume':
                self._printer.resume_print()

        def __process_cmd__(cmd):
            for k, v in cmd.iteritems():
                if k == 'job':
                    __process_job_cmd__(v)

        msgDict = json.loads(msg)
        for k, v in msgDict.iteritems():
            if k == 'cmd':
                __process_cmd__(v)


    @backoff.on_exception(backoff.constant, Exception, interval=5)
    def __probe_auth_token__(self):
        requests.get(self.config['api_host'] + "/api/ping", headers={"Authorization": "Bearer " + self.config['token']}).raise_for_status()

    def __start_mjpeg_capture__(self):
        q = Queue(maxsize=1)

        upstream_thread = threading.Thread(target=stream_up, args=(q,Config(self).load_config()))
        upstream_thread.daemon = True
        upstream_thread.start()

        self.webcam = self._settings.global_get(["webcam"])

        if self.webcam:
            producer = threading.Thread(target=capture_mjpeg, args=(self.webcam["stream"], q))
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

