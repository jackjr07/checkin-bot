#!/usr/bin/env python3

# This is a basic Rocket Bot which uses the realtime API (with a dash of REST api).
# You are meant to create a subclass and override relevant methods. (Namely, handle_message and handle_result).
# There're a lot of bindings to the APIs that this bot doesn't implement.
# If you'd like those features, feel free to implement them!
# 10/5/18 kimani (Dylan Abraham)

import os
import yaml
import re
import yaml
import json
import psycopg2

import rocketbot

from datetime import datetime

MY_USERNAME = 'wanitkun_cat'
DBHOST = 'db.cecs.pdx.edu'
DBNAME = 'wanitkun_cat'
UNAME ='wanitkun_cat'
PASS = 'epz5S5m*as'

conn=psycopg2.connect("host={} dbname={} user={} password={}".format(DBHOST, DBNAME, UNAME, PASS))

cur = conn.cursor()

# Example Bot Class
# Says hello to people who start a message by mentioning it.
class HelloBot(rocketbot.WebsocketRocketBot):
 # Override the handle_message method to do our own thing.
# 	def handle_chat_message(self, message):
#		bot_mention = "@{}".format(self.user.lower())
#
#        	self.logger.info("Incoming message: {}".format(message))
#        	if message["text"].lower().startswith(bot_mention):
#            		self.respond("Hi, @" + message["user_name"]+ "MOMO HELPPP")
#        	elif not message["channel_name"].startswith("#"):
        # If msg
#            	self.respond("Hi, @" + message["user_name"])

	def handle_chat_message(self, message):
		time = datetime.now()
#		bot_mention = "checkin  @{}".format(self.user.lower())

		self.logger.info("Incoming message: {}".format(message))
		if message["user_name"].lower() != "jerrybot":

			if "checkin" in  message["text"].lower():
				self.respond("Hi, @" + message["user_name"] + " On desk: " + " {}".format(time))

# Main Method
if __name__ == "__main__":
    # Pull config from a config file
    dir = os.path.dirname(__file__)
    with open(os.path.join(dir, "rb.cfg"), 'r') as cfg_file:
        cfg = yaml.safe_load(cfg_file)
        domain = cfg["domain"]
        user = cfg["user"]
        password = cfg["password"]

    # Create the bot
    bot = HelloBot(domain, user, password)

    # Make the bot run
    bot.start()
