# coding=utf-8

########################################################################################################################
### Do not forget to adjust the following variables to your own plugin.

# The plugin's identifier, has to be unique
plugin_identifier = "anywhere"

# The plugin's python package, should be "octoprint_<plugin identifier>", has to be unique
plugin_package = "octoprint_anywhere"

# The plugin's human readable name. Can be overwritten within OctoPrint's internal data via __plugin_name__ in the
# plugin module
plugin_name = "OctoPrint Anywhere"

# The plugin's version. Can be overwritten within OctoPrint's internal data via __plugin_version__ in the plugin module
plugin_version = "1.1.1"

# The plugin's description. Can be overwritten within OctoPrint's internal data via __plugin_description__ in the plugin
# module
plugin_description = """Control your OctoPrint from anywhere, using your smart phone"""

# The plugin's author. Can be overwritten within OctoPrint's internal data via __plugin_author__ in the plugin module
plugin_author = "Kenneth Jiang"

# The plugin's author's mail address.
plugin_author_email = "kenneth.jiang@gmail.com"

# The plugin's homepage URL. Can be overwritten within OctoPrint's internal data via __plugin_url__ in the plugin module
plugin_url = "https://github.com/kennethjiang/OctoPrint-Anywhere"

# The plugin's license. Can be overwritten within OctoPrint's internal data via __plugin_license__ in the plugin module
plugin_license = "AGPLv3"

# Any additional requirements besides OctoPrint should be listed here
plugin_requires = ["OctoPrint>=1.2.4", "backoff>=1.4.3", "raven"]

### --------------------------------------------------------------------------------------------------------------------
### More advanced options that you usually shouldn't have to touch follow after this point
### --------------------------------------------------------------------------------------------------------------------

# Additional package data to install for this plugin. The subfolders "templates", "static" and "translations" will
# already be installed automatically if they exist.
plugin_additional_data = ['bin']

# Any additional python packages you need to install with your plugin that are not contained in <plugin_package>.*
plugin_additional_packages = []

# Any python packages within <plugin_package>.* you do NOT want to install with your plugin
plugin_ignored_packages = []

# Additional parameters for the call to setuptools.setup. If your plugin wants to register additional entry points,
# define dependency links or other things like that, this is the place to go. Will be merged recursively with the
# default setup parameters as provided by octoprint_setuptools.create_plugin_setup_parameters using
# octoprint.util.dict_merge.
#
# Example:
#     plugin_requires = ["someDependency==dev"]
#     additional_setup_parameters = {"dependency_links": ["https://github.com/someUser/someRepo/archive/master.zip#egg=someDependency-dev"]}
additional_setup_parameters = {}

########################################################################################################################

from setuptools import setup

try:
	import octoprint_setuptools
except:
	print("Could not import OctoPrint's setuptools, are you sure you are running that under "
	      "the same python installation that OctoPrint is installed under?")
	import sys
	sys.exit(-1)

import sys
is_rpi = False
try:
    with open('/sys/firmware/devicetree/base/model', 'r') as firmware_model:
        if firmware_model.read().find('Raspberry Pi') > -1:
            is_rpi = True
except:
     pass
if is_rpi and not hasattr(sys, 'pypy_version_info'):
	plugin_requires += [ 'picamera==1.13' ]

setup_parameters = octoprint_setuptools.create_plugin_setup_parameters(
	identifier=plugin_identifier,
	package=plugin_package,
	name=plugin_name,
	version=plugin_version,
	description=plugin_description,
	author=plugin_author,
	mail=plugin_author_email,
	url=plugin_url,
	license=plugin_license,
	requires=plugin_requires,
	additional_packages=plugin_additional_packages,
	ignored_packages=plugin_ignored_packages,
	additional_data=plugin_additional_data
)

if len(additional_setup_parameters):
	from octoprint.util import dict_merge
	setup_parameters = dict_merge(setup_parameters, additional_setup_parameters)

setup(**setup_parameters)
