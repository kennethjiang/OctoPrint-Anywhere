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

import uuid
import tempfile
import os
import time
import struct
import shutil
import sys
import math
import copy
import flask
import serial
import serial.tools.list_ports
import binascii
import re
import collections
import json
import imp
import glob
import ctypes
import _ctypes
import platform
import subprocess
import psutil
import socket
import threading
import yaml
import logging
import logging.handlers

class SlicerPlugin(octoprint.plugin.SettingsPlugin,
				   octoprint.plugin.BlueprintPlugin):

	##~~ SettingsPlugin mixin

	def get_settings_defaults(self):
		return dict(
			# put your plugin's default settings here
		)

	##~~ Softwareupdate hook

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

	# Event monitor
	def on_event(self, event, payload) :

		# check if event is slicing started
		if event == octoprint.events.Events.SLICING_STARTED :

			# Set processing slice
			self.processingSlice = True

		# Otherwise check if event is slicing done, cancelled, or failed
		elif event == octoprint.events.Events.SLICING_DONE or event == octoprint.events.Events.SLICING_CANCELLED or event == octoprint.events.Events.SLICING_FAILED :

			# Clear processing slice
			self.processingSlice = False

	def __call__(self, *callback_args, **callback_kwargs):
		self._slicing_manager.delete_profile("cura", self.tempProfileName)

# If you want your plugin to be registered within OctoPrint under a different name than what you defined in setup.py
# ("OctoPrint-PluginSkeleton"), you may define that here. Same goes for the other metadata derived from setup.py that
# can be overwritten via __plugin_xyz__ control properties. See the documentation for that.
__plugin_name__ = "RemoteControl"

def __plugin_load__():
	global __plugin_implementation__
	__plugin_implementation__ = SlicerPlugin()

	global __plugin_hooks__
	__plugin_hooks__ = {
		"octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information
	}
