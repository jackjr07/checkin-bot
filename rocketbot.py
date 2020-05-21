import hashlib
import io
import json
import logging
import re
import requests
import sys
import uuid
import websocket
import traceback

# Base Class for Rocket.chat Bots
# You probably don't want to subclass this directly,
# You probably want to subclass
# WebsocketRocketBot or CGIRocketBot
class RocketBot:
    def __init__(self, user):
        self.user = user

        # Setup logging
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        # Uncomment during development to see lots of information
        #self.logger.setLevel(logging.DEBUG)

        stderr_logger = logging.StreamHandler()
        stderr_logger_formatter = logging.Formatter('[%(asctime)s %(levelname)s] %(message)s')
        stderr_logger.setFormatter(stderr_logger_formatter)
        self.logger.addHandler(stderr_logger)

    # Your main work function. Called whenever your bot gets a new message
    # in a channel it's in.
    def handle_chat_message(self, message):
        self.logger.warning("Unhandled chat message: {}".format(message))

    # Filters out message from yourself before
    # passing messages onto the handle_chat_message
    # handler
    def _handle_chat_message(self, message):
        try:
            if message['_rawMessage']['reactions']:
                self.logger.debug("Filtering out message updated by reactions")
                return
        except KeyError:
            pass
        try:
            if message['_rawMessage']['urls'][0]['meta']:
                self.logger.debug("Filtering out message URL preview")
                return
        except KeyError:
            pass
        try:
            # The biggest difference I saw in a not updated message is 58
            if (message['_rawMessage']['_updatedAt']['$date'] - message['timestamp']) > 200:
                self.logger.debug("Filtering out message from @Username update")
                return
        except KeyError:
            pass
        if message['user_name'] == self.user:
            self.logger.debug("Filtering out message from self")
            return
        elif message['bot']:
            self.logger.debug("Filtering out message from known bot")
            return
        else:
            self.handle_chat_message(message)

    # Respond to the incoming message
    def respond(self, text, attachments = None, channel = None):
        message = {
            "text": text,
            "attachments": attachments,
            "channel": channel
        }

        self.logger.warning("Not sending message because I don't know how: {}".format(message))

    def start(self):
        self.logger.warning("I'm an abstract base class, I don't do anything on my own")

# Web socket based RocketBot
# Unless you known otherwise, this is probably what you want to subclass
class WebsocketRocketBot(RocketBot):
    def __init__(self, domain, user, password, raise_exceptions=False):
        super().__init__(user)
        self.domain = domain
        self.web_socket_address="wss://{}/websocket".format(domain)
        self.passhash = hashlib.sha256(password.encode('utf-8')).hexdigest()
        self.raise_exceptions = raise_exceptions
        self.logged_in = False
        self.login_id = str(uuid.uuid4())
        self._room_requests = {}
        # Joined room list and all rooms
        self.room_list = {}
        self.all_room_list = {}
        self.room_list_by_id = {}
        self.all_room_list_by_id = {}

    # Filters out previously read messages before passing
    # messages on to the generic _handle_chat_message method
    def _handle_chat_message(self, message):
        if "unread" in message["_rawMessage"]:
            super()._handle_chat_message(message)
        else:
            self.logger.debug("Filtering out known read message")
            return

    # Opens the server connection
    def _connect(self):
        self.logger.info("Connecting to {}\n".format(self.web_socket_address))
        # Send Connection Request
        connect_request = {
            "msg": "connect",
            "version": "1",
            "support": ["1", "pre2", "pre1"]
        }
        self.ws.send(json.dumps(connect_request))

    # Sends a login request
    def _login(self):
        self.logger.info("Logging in as {}\n".format(self.user))
        login_request = {
            "msg": "method",
            "method": "login",
            "id": self.login_id,
            "params": [
                {
                    "user": {"username": self.user},
                    "password": {
                        "digest": self.passhash,
                        "algorithm":"sha-256"
                    }
                }
            ]
        }
        self.ws.send(json.dumps(login_request))

    # Join a room
    def join_room(self, room_name):
        self.logger.info("Joining room: {}".format(room_name))
        # Make sure we've reached a point where we can join rooms
        if not self.logged_in:
            raise AssertionError("Called join_room without being logged in")

        room = self.room_list.get(room_name)

        if room is None:
            raise AssertionError("Requested room does not exist")

        id = str(uuid.uuid4())

        # Prepare join request
        join_request = {
            "msg": "method",
            "method": "joinRoom",
            "id": id,
            "params": [
                room["_id"],
            ]
        }
        # Track outstanding requests
        self._room_requests[id] = room
        # Send join request
        self.ws.send(json.dumps(join_request))

    # Subscribe to all messages from a room
    def _subscribe_room(self, room):
        if not self.logged_in:
            raise AssertionError("Called _subscribe_room without being logged in")

        id = str(uuid.uuid4())
        self.logger.info("Subscribing to room {}".format(room["_catName"]))
        self.logger.debug("Subscribing to room {}".format(json.dumps(room)))
        subscribe_request = {
            "msg": "sub",
            "id": id,
            "name": "stream-room-messages",
            "params": [
                room["_id"],
                False
            ]
        }
        self.ws.send(json.dumps(subscribe_request))

    def _subscribe_to_self_events(self):
        if not self.logged_in:
            raise AssertionError("Called subscribe_to_self_events without being logged in")

        id = str(uuid.uuid4())
        self.logger.info("Subscribing to self events")
        self._user_event_key = "{}/rooms-changed".format(self.user_id)
        subscribe_request = {
            "msg": "sub",
            "id": id,
            "name": "stream-notify-user",
            "params":[
                self._user_event_key,
                False
            ]
        }
        self.ws.send(json.dumps(subscribe_request))

    # Play ping pong (keepalive)
    def _send_pong(self):
        ping_reply = {
            "msg": "pong"
        }

        self.logger.debug("Sending pong: {}".format(json.dumps(ping_reply)))
        self.ws.send(json.dumps(ping_reply))

    # Auto subscribe to channels upon @ or DM
    def _handle_room_event(self, message):
        self.logger.debug("Incoming room event: {}".format(message))
        channel = message[1]
        cid = channel["_id"]
        # If channel is chat/private chat/livechat
        if channel["t"] in ("c", "p", "l"):
            cname = "#{}".format(channel["name"])
        # or channel is instant message
        else:
            my_ims = self._rest_api_get("/api/v1/im.list")["ims"]
            for im in my_ims:
                im_users = list(im["usernames"])
                im_users.remove(self.user)
                imname = "_".join(sorted(im_users))
                if im["_id"] == cid:
                    cname = imname
                    break
        channel["_catName"] = cname

        # If channel is not subscribed it's not in room_list
        if self.room_list.get(cname) is None:
            self.room_list[cname] = channel
            self.room_list_by_id[cid] = channel
            self._subscribe_room(channel)

    # Override this with your own message handler
    def _handle_message(self, message):
        if "server_id" in message:
            self._server_id = message["server_id"]
            return

        command = message["msg"]

        # Table Tennis!
        if command == "ping":
            self._send_pong()

        # Server acks connections, send login request
        elif command == "connected":
            self._login()

        # We got a result.
        elif command == "result":
            result_id = message.get("id")
            # Answer to our login request
            if result_id == self.login_id:
                self.logged_in = True
                self.user_id = message["result"]["id"]
                self.user_token = message["result"]["token"]
                self._handle_logged_in(message)
            # Pass result to generic handler
            else:
                self.handle_result(message)

        # Pass message to handler
        elif command == "ready":
            self.handle_ready(message)
        elif command == "changed":
            # Some room change notification
            if message["fields"]["eventName"] == self._user_event_key:
                self._handle_room_event(message["fields"]["args"])
            # Assuming this is a message
            else:
                # Get the args dict out of the message
                args = message["fields"]["args"][0]

                # Get some arguments from the argsdict
                room_id = args["rid"]
                room = self.room_list_by_id[room_id]["_catName"]

                # Make a dict that looks like a message you'd get from an outgoing integration
                api_style_message = {
                    "token": None, # No tokens when using web sockets :)
                    "bot": False, # TODO: Have no data, should maybe query user info separately if unknown
                    "channel_id": room_id,
                    "channel_name": room,
                    "message_id": args["_id"],
                    "timestamp": args["ts"]["$date"], # TODO: Wrong format, needs strftime'd
                    "user_id": args["u"]["_id"],
                    "user_name": args["u"]["username"],
                    "text": args["msg"],
                    "isEdited": True if args.get("editedBy") is not None else False,
                    "_rawMessage": args,
                }

                self._last_message_channel = room

                self._handle_chat_message(api_style_message)
        else:
            self.handle_unknown(message)

    # Override this with your own results handler (if desired)
    def handle_result(self, message):
        self.logger.debug("Unhandled result event: {}".format(message))

    # Override this with your own ready handler (if desired)
    def handle_ready(self, message):
        self.logger.debug("Unhandled ready event: {}".format(message))

    # Override this with your own handler for unknown messages (if desired)
    def handle_unknown(self, message):
        self.logger.debug("Unhandled unknown event: {}".format(message))

    # Send a message to a channel
    def send_message(self, text, channel_name, attachments = None):

        if attachments == None:
            real_attachments = []
        else:
            real_attachments = attachments

        if not self.logged_in:
            raise AssertionError("Not logged in")
        room_id = self.room_list[channel_name]["_id"]
        message = {
            "_id": str(uuid.uuid4()),
            "rid": room_id,
            "msg": text,
            "attachments": attachments
        }

        if attachments != None:
            message["parseUrls"] = False

        msg_request = {
            "msg": "method",
            "method": "sendMessage",
            "id": str(uuid.uuid4()),
            "params": [message]
        }

        self.logger.debug("Sending message: {}".format(json.dumps(msg_request)))
        self.ws.send(json.dumps(msg_request))

    def respond(self, text, attachments = None, channel = None):
        if not self._last_message_channel:
            raise AssertionError("No message to respond to")
        if not channel:
            channel = self._last_message_channel
        self.send_message(text, channel, attachments)

    def _rest_api_get(self, api_method):
        rest_api_endpoint = "https://{}{}".format(self.domain, api_method)
        if not self.logged_in:
            raise AssertionError("Not logged in")
        r = requests.get(rest_api_endpoint,
                         headers = {
                             "X-Auth-Token" : self.user_token,
                             "X-User-Id": self.user_id
                         })
        response_json = r.json()
        return response_json

    # Ask the REST api for a list of all public channels. Used for ID lookups.
    def populate_room_list(self):
        rooms = self._rest_api_get("/api/v1/channels.list")
        channels = rooms["channels"]
        for channel in channels:
            cname = "#{}".format(channel["name"])
            cid = channel["_id"]
            self.all_room_list[cname] = channel
            self.all_room_list_by_id[cid] = channel

    def _subscribe_to_joined_rooms(self):
        my_channels = self._rest_api_get("/api/v1/channels.list.joined")["channels"]
        for channel in my_channels:
            cname = "#{}".format(channel["name"])
            cid = channel["_id"]
            channel["_catName"] = cname
            self.room_list[cname] = channel
            self.room_list_by_id[cid] = channel
            self._subscribe_room(channel)
        my_groups = self._rest_api_get("/api/v1/groups.list")["groups"]
        for group in my_groups:
            gname = "#{}".format(group["name"])
            gid = group["_id"]
            group["_catName"] = gname
            self.room_list[gname] = group
            self.room_list_by_id[gid] = group
            self._subscribe_room(group)
        my_ims = self._rest_api_get("/api/v1/im.list")["ims"]
        for im in my_ims:
            im_users = list(im["usernames"])
            im_users.remove(self.user)
            imname = "_".join(sorted(im_users))
            imid = im["_id"]
            im["_catName"] = imname
            self.room_list[imname] = im
            self.room_list_by_id[imid] = im
            self._subscribe_room(im)

    def _handle_logged_in(self, message):
        self._subscribe_to_joined_rooms()
        self._subscribe_to_self_events()
        # TODO: Need to subscribe to https://rocket.chat/docs/developer-guides/realtime-api/subscriptions/stream-notify-user/
        self.bot_ready()

    def bot_ready(self):
        self.logger.info("Bot ready now")

    def start(self):
        self.ws = websocket.create_connection(self.web_socket_address)
        self._connect()
        while True:
            msg = self.ws.recv()

            message = json.loads(msg)
            self.logger.debug("Web socket message: {}".format(json.dumps(message)))
            try:
                self._handle_message(message)
            except Exception as e:
                self.logger.error("Error handling message: {}".format(e))
                self.logger.debug(''.join(traceback.format_exception(type(e), e, e.__traceback__, limit=None, chain=True)))
                if self.raise_exceptions:
                    raise(e)

# CGI based RocketBot
# Uses the Rocket.chat integrations API
class CGIRocketBot(RocketBot):
    def __init__(self, user, token):
        super().__init__(user)
        self.token = token
        self._responded = False
        # Replace stdin reader with one that can decode UTF-8
        sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8')

    # Filters out messages that don't include the correct token
    # messages on to the generic _handle_chat_message method
    def _handle_chat_message(self, message):
        if not "token" in message:
            self.logger.debug("Filtering out message with no token")
        elif message["token"] != self.token:
            self.logger.debug("Filtering out message an invalid token")
        else:
            super()._handle_chat_message(message)

    # Respond to the incoming message
    def respond(self, text, attachments = None, channel = None):
        response = {
            "text": text,
            "attachments": attachments,
            "channel": channel
        }

        if self._responded:
            self.logger.warning("Trying to respond more than once: {}".format(json.dumps(response)))
            return
        else:
            self.logger.info("Responding: {}".format(json.dumps(response)))
            self._responded = True
            print("Content-Type: application/json")
            print()
            print(json.dumps(response))

    # Respond to the incoming message with a null response
    def _bail(self):
        print("Content-Type: application/json")
        print()
        print('{}')

    def start(self):
        body = sys.stdin.read()
        body_json = json.loads(body)
        self.logger.debug("Incoming message: {}".format(json.dumps(body_json)))
        self._handle_chat_message(body_json)
        if not self._responded:
            self._bail()
