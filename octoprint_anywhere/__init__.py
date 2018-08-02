# coding=utf-8
from __future__ import absolute_import

import time
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
from .utils import ip_addr

class AnywherePlugin(octoprint.plugin.SettingsPlugin,
                     octoprint.plugin.AssetPlugin,
                     octoprint.plugin.TemplatePlugin,
                     octoprint.plugin.StartupPlugin,
                     octoprint.plugin.SimpleApiPlugin,
                     octoprint.plugin.WizardPlugin,):

    ##~~ AssetPlugin mixin
    def get_assets(self):
        return dict(
                js=["js/anywhere.js"]
                )

    ##########
    ### Wizard
    ##########

    def is_wizard_required(self):
        return not self.config['registered']

    def get_wizard_version(self):
        return 4
        # Wizard version numbers used in releases
        # < 1.4.2 : no wizard
        # 1.4.2 : 1
        # 1.4.3 : 1


    ################
    ### Plugin APIs
    ################

    def get_api_commands(self):
        return dict(
            reset_config=[],
            get_config=[],
        )

    def is_api_adminonly(self):
        return True

    def on_api_command(self, command, data):
        import flask
        if command == "reset_config":
            old_token = self.config['token']
            self.config.reset_config()
            self.ss.disconnect()   # Server WS connection needs to be reset to pick up new token
            return flask.jsonify(reg_url="{0}/pub/link_printer?token={1}&copy_from={2}".format(self.config['api_host'], self.config['token'], old_token), registered=self.config['registered'])
        elif command == "get_config":
            return flask.jsonify(reg_url="{0}/pub/link_printer?token={1}".format(self.config['api_host'], self.config['token']), registered=self.config['registered'])


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

    def on_after_startup(self):
        self.config = Config(self)

        try:
            self.message_q = Queue(maxsize=128)
            self.webcam_q  = Queue(maxsize=1)
            self.remote_status = {"watching": False}

            main_thread = threading.Thread(target=self.__start_server_connections__)
            main_thread.daemon = True
            main_thread.start()

            # Thread to capture mjpeg from mjpeg_streamer
            self.__start_mjpeg_capture__()

            # listen to OctoPrint websocket. It's in another thread, which is implemented by OctoPrint code
            listen_to_octoprint(self._settings.settings, self.message_q, lambda _: self.__send_heartbeat__())
        except:
            self.config.sentry.captureException()
            import traceback; traceback.print_exc()

    def __start_server_connections__(self):
        try:
            # Forever loop to block other server calls if token is registered with server
            if (not self.config['registered']):
                self.__probe_auth_token__()
                self.config['registered'] = True

            ws_thread = threading.Thread(target=self.__message_loop__)
            ws_thread.daemon = True
            ws_thread.start()

            upstream_thread = threading.Thread(target=stream_up, args=(self.webcam_q, self.config, self._printer, self.remote_status))
            upstream_thread.daemon = True
            upstream_thread.start()
        except:
            self.config.sentry.captureException()
            import traceback; traceback.print_exc()

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

        def __process_temps_cmd__(cmd):
            if 'set' in cmd:
                self._printer.set_temperature(cmd['set']['heater'], cmd['set']['target'])

        def __process_jog_cmd__(cmd):
            axis = cmd.keys()[0]
            if isinstance(cmd[axis], int):
                self._printer.jog(cmd)
            else:
                self._printer.home(axis)

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


    def __probe_auth_token__(self):
        while True:
            try:
                requests.get(self.config['api_host'] + "/api/ping", headers={"Authorization": "Bearer " + self.config['token']}).raise_for_status()
                return
            except:
                time.sleep(5)

    def __start_mjpeg_capture__(self):
        try:
            self.webcam = self._settings.global_get(["webcam"])

            if self.webcam:
                producer = threading.Thread(target=capture_mjpeg, args=(self.webcam, self.webcam_q))
                producer.daemon = True
                producer.start()
        except:
            self.config.sentry.captureException()
            import traceback; traceback.print_exc()

    def __send_heartbeat__(self):
        try:
            octolapse = self._plugin_manager.get_plugin_info('octolapse')
            self.message_q.put(json.dumps({
                'hb': {
                    'ipAddrs': ip_addr(),
                    'settings': {
                        'temperature': self._settings.settings.effective['temperature']
                    },
                    'octolapse': {'version': octolapse.version, 'enabled': octolapse.enabled} if octolapse else None,
                },
                'origin': 'oa',
                'oaVersion': self._plugin_version
            }, encoding='latin1'))
        except:
            self.config.sentry.captureException()
            import traceback; traceback.print_exc()


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

