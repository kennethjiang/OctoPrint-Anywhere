import octoprint_client

def listen_to_octoprint(settings):
    def on_connect(ws):
        print(">>> Connected!")

    def on_close(ws):
        print(">>> Connection closed!")

    def on_error(ws, error):
        print("!!! Error: {}".format(error))

    def on_heartbeat(ws):
        print("<3")

    def on_message(ws, message_type, message_payload):
        print("Message: {}, Payload: {}".format(message_type, json.dumps(message_payload)))

    octoprint_client.init_client(settings)
    socket = octoprint_client.connect_socket(on_connect=on_connect,
                                             on_close=on_close,
                                             on_error=on_error,
                                             on_heartbeat=on_heartbeat,
                                             on_message=on_message)

    print(">>> Waiting for client to exit")
    try:
        socket.wait()
    finally:
        print(">>> Goodbye...")
