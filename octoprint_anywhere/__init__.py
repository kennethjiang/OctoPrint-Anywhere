# coding=utf-8
from __future__ import absolute_import

import octoprint.plugin

import os
import threading
import time
import requests
import backoff
from raven import breadcrumbs

from .message_loop import MessageLoop
from .config import Config

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

            self.main_loop.quit()
            self.start_main_thread()

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
        self.start_main_thread()


    ##~~ Eventhandler mixin

    def on_event(self, event, payload):
        # Event may be triggered before object is properly initialized
        if not hasattr(self, 'main_loop') or not hasattr(self, 'config') or not self.config['registered']:
            return

        if event.startswith("Print"):
            self.main_loop.send_octoprint_data(event, payload)


    ## Internal functions

    def start_main_thread(self):
        try:
            main_thread = threading.Thread(target=self.__run_message_loop__)
            main_thread.daemon = True
            main_thread.start()
        except:
            self.config.sentry.captureException()
            import traceback; traceback.print_exc()

    def __run_message_loop__(self):
        # Forever loop to block other server calls if token is registered with server
        if (not self.config['registered']):
            self.__probe_auth_token__()
            self.config['registered'] = True

        dev_settings = self.__get_dev_settings__()
        self.main_loop = MessageLoop(self.config, self, dev_settings)
        self.main_loop.run_until_quit()

    @backoff.on_exception(backoff.expo, Exception, max_value=120)
    def __get_dev_settings__(self):
        r = requests.get(self.config['stream_host'] + "/api/dev_settings", headers={"Authorization": "Bearer " + self.config['token']})
        r.raise_for_status()
        return r.json()

    def __probe_auth_token__(self):
        while True:
            try:
                requests.get(self.config['stream_host'] + "/api/ping", headers={"Authorization": "Bearer " + self.config['token']}).raise_for_status()
                return
            except:
                time.sleep(5)


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

