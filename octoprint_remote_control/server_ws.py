# coding=utf-8

import time
from threading import Thread
import websocket

class ServerSocket:
    def on_message(self, ws, message):
        print message

    def on_error(self, ws, error):
        print error

    def on_close(self, ws):
        print "### closed ###"

    def __init__(self, url, token):
        #websocket.enableTrace(True)
        self.ws = websocket.WebSocketApp(url,
                                  on_message = self.on_message,
                                  on_error = self.on_error,
                                  on_close = self.on_close,
                                  header = ["Authorization: Bearer " + token],
                                  subprotocols=["binary", "base64"])

    def run(self):
        self.ws.run_forever()

    def send_binary(self, data):
        self.ws.send(data, websocket.ABNF.OPCODE_BINARY)

    def send_text(self, data):
        self.ws.send(data)

    def connected(self):
        return self.ws.sock and self.ws.sock.connected

    def disconnect(self):
        self.ws.close()

if __name__ == "__main__":
    ss = ServerSocket("ws://localhost:6001/app/ws", "1234")
    wst = Thread(target=ss.run)
    wst.daemon = True
    wst.start()
    while True:
        aaa = open("/Users/kenneth/.rvm/gems/ruby-2.2.4/gems/xcpretty-0.2.4/features/fixtures/xcodebuild.log").read()
        ss.send_binary(aaa)
        print len(aaa)
