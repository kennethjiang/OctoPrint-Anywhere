# coding=utf-8
from __future__ import absolute_import

from octoprint import settings

def produce:
	import pdb; pdb.set_trace()
	settings.get(["webcam", "stream"])
	res = requests.get('http://jfalco3dp.ddns.net/webcam/?action=stream&1491831111684', stream=True)
