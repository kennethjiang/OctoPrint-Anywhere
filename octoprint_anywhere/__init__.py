# coding=utf-8
from __future__ import absolute_import

import time
import octoprint.plugin
import json

import logging
import os
import threading
from Queue import Queue
import requests
from raven import breadcrumbs

from .mjpeg_stream import stream_up
from .timelapse import upload_timelapses
from .server_ws import ServerSocket
from .config import Config
from .remote_status import RemoteStatus
from .utils import ip_addr, ExpoBackoff

class AnywherePlugin(octoprint.plugin.SettingsPlugin,
                     octoprint.plugin.AssetPlugin,
                     octoprint.plugin.EventHandlerPlugin,
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
            self.op_info = self.__gather_op_info__()
            self.remote_status = RemoteStatus()

            main_thread = threading.Thread(target=self.__start_server_connections__)
            main_thread.daemon = True
            main_thread.start()
        except:
            self.config.sentry.captureException()
            import traceback; traceback.print_exc()

    def __start_server_connections__(self):
        try:
            # Forever loop to block other server calls if token is registered with server
            if (not self.config['registered']):
                self.__probe_auth_token__()
                self.config['registered'] = True

            stream_host = self.config['stream_host']
            token = self.config['token']
            upstream_thread = threading.Thread(target=stream_up, args=(stream_host, token, self._printer, self.remote_status, self._settings.global_get(["webcam"]), self.config.sentry))
            upstream_thread.daemon = True
            upstream_thread.start()

            timelapse_upload_thread = threading.Thread(target=upload_timelapses, args=(stream_host, token, self._settings.settings.getBaseFolder("timelapse")))
            timelapse_upload_thread.daemon = True
            timelapse_upload_thread.start()

            self.__message_loop__()
        except:
            self.config.sentry.captureException()
            import traceback; traceback.print_exc()

    def __message_loop__(self):
        last_heartbeat = 0

        backoff = ExpoBackoff(1200)
        while True:
            try:

                self.__connect_server_ws__()
                time.sleep(2)  # Allow the time for server ws to connect
                while self.ss.connected():
                    breadcrumbs.record(message="Message loop for: " + self.config['token'])
                    if time.time() - last_heartbeat > 60:
                        self.__send_heartbeat__()
                        last_heartbeat = time.time()

                    self.__send_octoprint_data__()
                    backoff.reset()
                    time.sleep(10)

            finally:
                try:
                    self.ss.close()
                except:
                    pass
                backoff.more()   # When it gets here something is wrong. probably network issues. Pause before retry

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
                requests.get(self.config['stream_host'] + "/api/ping", headers={"Authorization": "Bearer " + self.config['token']}).raise_for_status()
                return
            except:
                time.sleep(5)

    def __send_octoprint_data__(self, event_type=None, event_payload=None):
        try:
            data = self._printer.get_current_data()
            data['temps'] = self._printer.get_current_temperatures()
            data['origin'] = 'octoprint'
            if event_type:
                data['type'] = event_type
                data['payload'] = event_payload

            self.ss.send_text(json.dumps(data))
        except:
            self.config.sentry.captureException()
            import traceback; traceback.print_exc()

    def __send_heartbeat__(self):
        try:
            self.ss.send_text(json.dumps({
                'hb': {
                    'ipAddrs': self.op_info['ip_addrs'],
                    'settings': self.op_info['settings'],
                    'octolapse': self.op_info['octolapse'],
                },
                'origin': 'oa',
                'oaVersion': self._plugin_version
            }, encoding='latin1'))
        except:
            self.config.sentry.captureException()
            import traceback; traceback.print_exc()

    def __gather_op_info__(self):
        octolapse = self._plugin_manager.get_plugin_info('octolapse')
        return {
                'ip_addrs': ip_addr(),
                'octolapse': {'version': octolapse.version, 'enabled': octolapse.enabled} if octolapse else None,
                'settings': {
                        'temperature': self._settings.settings.effective['temperature']
                    }
                }

    ##~~ Eventhandler mixin

    def on_event(self, event, payload):
        if event.startswith("Print"):
            if hasattr(self, 'ss') and self.ss.connected():
                breadcrumbs.record(message="Event handler for: " + self.config['token'])
                self.__send_octoprint_data__(event, payload)


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

