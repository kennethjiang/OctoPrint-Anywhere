# coding=utf-8
from __future__ import absolute_import
import logging
import backoff
from contextlib import closing
import requests

_logger = logging.getLogger(__name__)

@backoff.on_exception(backoff.expo, Exception, max_value=60)
@backoff.on_predicate(backoff.constant, interval=600)
def upload_timelapses(cfg):
    r = requests.get(cfg['stream_host'] + "/timelapses/", headers={"Authorization": "Bearer " + cfg['token']})
    r.raise_for_status()
    timelapses = r.json()
    if not timelapses['device']['octolapseOptedIn']:
        return false

if __name__ == "__main__":
    class ConfigStub:
        def __init__(self, path):
            self.p = path

        def load_config(self):
            import yaml
            with open(self.p, 'r') as stream:
                return yaml.load(stream)

    import logging
    logging.basicConfig()
    logging.getLogger().setLevel(logging.DEBUG)
    req_log = logging.getLogger('requests.packages.urllib3')
    req_log.setLevel(logging.DEBUG)
    req_log.propagate = True
    import sys

    upload_timelapses(ConfigStub(sys.argv[1]).load_config())
