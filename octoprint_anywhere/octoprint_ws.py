import json
import octoprint_client
from .utils import ip_addr

def listen_to_octoprint(settings, q):
    def on_error(ws, error):
        print("!!! Error: {}".format(error))

    def on_heartbeat(ws):
        q.put(json.dumps({'hb': {'ipAddrs': ip_addr()}}))

    def on_message(ws, message_type, message_payload):

        def __deplete_queue__(q):
            while q.qsize() > 10:
                q.get_nowait()

        if type(message_payload) is not dict:
            return

        __deplete_queue__(q)
        q.put(json.dumps(message_payload))

    if "init_client" in dir(octoprint_client): # OctoPrint <= 1.3.2
        octoprint_client.init_client(settings)
        socket = octoprint_client.connect_socket(on_connect=on_connect,
                                             on_close=on_close,
                                             on_error=on_error,
                                             on_heartbeat=on_heartbeat,
                                             on_message=on_message)
    else:
        host = settings.get(["server", "host"])
        host = host if host != "0.0.0.0" else "127.0.0.1"
        port = settings.getInt(["server", "port"])
        apikey = settings.get(["api", "key"])
        baseurl = octoprint_client.build_base_url(host=host, port=port)
        client = octoprint_client.Client(baseurl, apikey)
        client.create_socket(on_error=on_error,
                 on_heartbeat=on_heartbeat,
                 on_message=on_message)
