# coding=utf-8

import time
import websocket

class ServerSocket:
    def __init__(self, url, token, on_server_ws_msg):
        #websocket.enableTrace(True)

        def on_message(ws, msg):
            on_server_ws_msg(ws, msg)

        def on_error(ws, error):
            pass

        self.ws = websocket.WebSocketApp(url,
                                  on_message = on_message,
                                  on_error = on_error,
                                  header = ["Authorization: Bearer " + token],
                                  subprotocols=["binary", "base64"])

    def run(self):
        self.ws.run_forever()

    def send_text(self, data):
        if self.connected():
            self.ws.send(data)

    def connected(self):
        return self.ws.sock and self.ws.sock.connected

    def disconnect(self):
        self.ws.keep_running = False;
        self.ws.close()
