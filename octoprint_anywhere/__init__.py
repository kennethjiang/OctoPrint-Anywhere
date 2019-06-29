# coding=utf-8
from __future__ import absolute_import

import octoprint.plugin

import os
import threading
import time
import requests
import backoff
from raven import breadcrumbs
import logging

from .message_loop import MessageLoop
from .config import Config

PRINTQ_FOLDER = "OctoPrint-Anywhere"

class AnywherePlugin(octoprint.plugin.SettingsPlugin,
                     octoprint.plugin.AssetPlugin,
                     octoprint.plugin.EventHandlerPlugin,
                     octoprint.plugin.TemplatePlugin,
                     octoprint.plugin.StartupPlugin,
                     octoprint.plugin.SimpleApiPlugin,
                     octoprint.plugin.WizardPlugin,):

    def __init__(self):
        self.current_gcodefile_id = None

    ##~~ AssetPlugin mixin
    def get_assets(self):
        return dict(
                js=["js/anywhere.js"]
                )

    ##########
    ### Wizard
    ##########

    def is_wizard_required(self):
        return not self.get_config()['registered']

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
            old_token = self.get_config()['token']
            self.get_config().reset_config()

            self.main_loop.quit()
            self.start_main_thread()

            return flask.jsonify(reg_url="{0}/pub/link_printer?token={1}&copy_from={2}".format(self.get_config()['api_host'], self.get_config()['token'], old_token), registered=self.get_config()['registered'])
        elif command == "get_config":
            conf = self.get_config().as_dict()
            conf.update(dict(picamera_error=self.config.picamera_error()))
            return flask.jsonify(conf)

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

    def on_startup(self, host, port):
        self.octoprint_port = port if port else self._settings.getInt(["server", "port"])

    def on_after_startup(self):
        self.get_config()
        self.__ensure_storage__()
        self.start_main_thread()


    ##~~ Eventhandler mixin

    def on_event(self, event, payload):
        # Event may be triggered before object is properly initialized
        if not hasattr(self, 'main_loop') or not hasattr(self, 'config') or not self.get_config()['registered']:
            return

        if event.startswith("Print"):

            if self.current_gcodefile_id:
                payload['gcodefile_id'] = self.current_gcodefile_id

            if event == 'PrintFailed' or event == 'PrintDone':
                self.current_gcodefile_id = None

            self.main_loop.send_octoprint_data(event, payload)


    ## Internal functions

    def get_config(self):
        try:
            return self.config
        except AttributeError:
            self.config = Config(self)
            return self.config

    def start_main_thread(self):
        try:
            main_thread = threading.Thread(target=self.__run_message_loop__)
            main_thread.daemon = True
            main_thread.start()
        except:
            self.get_config().sentry.captureException()
            import traceback; traceback.print_exc()

    def __run_message_loop__(self):
        # Forever loop to block other server calls if token is registered with server
        if (not self.get_config()['registered']):
            self.__probe_auth_token__()
            self.get_config()['registered'] = True

        dev_settings = self.__get_dev_settings__()
        self.get_config().set_dev_settings(dev_settings)

        self.main_loop = MessageLoop(self.get_config(), self)
        self.main_loop.run_until_quit()

    @backoff.on_exception(backoff.expo, Exception, max_value=120)
    def __get_dev_settings__(self):
        r = requests.get(self.config['stream_host'] + "/api/dev_settings", headers={"Authorization": "Bearer " + self.config['token']})
        r.raise_for_status()
        return r.json()

    def __probe_auth_token__(self):
        while True:
            try:
                requests.get(self.get_config()['stream_host'] + "/api/ping", headers={"Authorization": "Bearer " + self.get_config()['token']}).raise_for_status()
                return
            except:
                time.sleep(5)

    def start_print(self, print_to_start):
        self._logger.info('Received print command for gcodfile_id: {} '.format(print_to_start['id']))
        self.current_gcodefile_id = print_to_start['id']
        file_url = print_to_start['url']
        file_name = print_to_start['filename']
        print_thread = threading.Thread(target=self.__download_and_print__, args=(file_url, file_name))
        print_thread.daemon = True
        print_thread.start()

    def __download_and_print__(self, file_url, file_name):
        self.main_loop.send_octoprint_data('DownloadStarted', {'gcodefile_id': self.current_gcodefile_id})
        r = requests.get(file_url, allow_redirects=True)
        r.raise_for_status()
        target_path = os.path.join(self._g_code_folder, file_name)
        open(target_path, "wb").write(r.content)
        self._logger.info('Finished downloading to target_path: {}'.format(target_path))
        self._printer.select_file(target_path, False, printAfterSelect=True)

    def __ensure_storage__(self):
        self._file_manager.add_folder("local", PRINTQ_FOLDER, ignore_existing=True)
        self._g_code_folder = self._file_manager.path_on_disk("local", PRINTQ_FOLDER)


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

