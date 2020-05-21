#!/usr/bin/python3
import os
import yaml
import re
import yaml
import json
import psycopg2

import rocketbot

#IP CHECK ON DESK
import socket
import uuid
import requests
import subprocess
from datetime import datetime

MY_USERNAME = '#'
DBHOST = '#'
DBNAME = '#'
UNAME ='#'
PASS = '#'

conn=psycopg2.connect("host={} dbname={} user={} password={}".format(DBHOST, DBNAME, UNAME, PASS))
conn.autocommit = True
cur = conn.cursor()

class Jaxbot(rocketbot.WebsocketRocketBot):
 
    def handle_chat_message(self, message):
        conn.rollback()
#        name = input_json['user_name']
        macaddr = hex(uuid.getnode())
        hostname = socket.gethostname()
        time = datetime.now()
        ip_request = requests.get('https://get.geojs.io/v1/ip.json')
        my_ip = ip_request.json()['ip']

        process = subprocess.Popen(["ip addr show ens3 | grep 'inet ' | awk '{print $2}' | cut -f1 -d'/'"],shell = True, stdout=subprocess.PIPE)
        stdout = process.communicate()[0]
#        print('IP:{}'.format(stdout))

        self.logger.info("Incoming message: {}".format(message))
        if message["user_name"].lower() != "jerrybot":
            if "checkin" in  message["text"].lower():
#                if (macaddr.find("90b11c9d7834") != -1): # "0x90b11c9d7834" in macaddr or "0x180373202fcb" in macaddr:
                    self.respond("Hi, @" + message["user_name"] + " On desk: " + " {}".format(time))
#                    self.respond("{}".format(macaddr))
                    self.respond("{}".format(hostname))
#                    self.respond("{}".format(my_ip))
                    self.respond("{}".format(stdout))
#        else:
#            self.respond("You're not on CATS desk location-Please login on desk")
#        cur.execute('INSERT INTO checkin (name) VALUES ("testdb1")')
        conn.commit()
        conn.close
     



# Main Method
if __name__ == "__main__":
#     Pull config from a config file
    dir = os.path.dirname(__file__)
    with open(os.path.join(dir, "rb.cfg"), 'r') as cfg_file:
        cfg = yaml.safe_load(cfg_file)
        domain = cfg["domain"]
        user = cfg["user"]
        password = cfg["password"]

    # Create the bot
    bot = Jaxbot(domain, user, password)

    # Make the bot run
    bot.start()
