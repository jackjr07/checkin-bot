#import uuid

#print(hex(uuid.getnode()))

#import pygeoip
#gi = pygeoip.GeoIP('GeoIP.dat')

import subprocess

subprocess.call("ls -lha", shell=True)


