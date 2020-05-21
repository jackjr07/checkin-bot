#import requests

#ip_request = requests.get('https://get.geojs.io/v1/ip.json')
#my_ip = ip_request.json()['ip']
#print (my_ip)
# get only ip add || ip addr show eth0 | grep 'inet ' | awk '{print $2}' | cut -f1 -d'/'

import subprocess
#host = raw_input("Enter a host to ping: ")

#p1 = subprocess.Popen(['ping','-c 2', host], stdout=subprocess.PIPE)

#output = p1.communicate()[0]

#print(output)
##########################

#p1 = subprocess.Popen(["ip addr show ens3 | grep 'inet ' | awk '{print $2}' | cut -f1 -d'/'"], stdout=subprocess.PIPE)

#output = p1.communicate()[0]
#print (output)
###############################
#subprocess.call(["ls", "-l"])

#p = subprocess.check_output(["echo", "Jax"])
#print ("p =", p)
####################################

#subprocess.call("ip addr show ens3 | grep 'inet' | awk '{print $2}' | cut -f1 -d'/' ", shell = True)

process = subprocess.Popen(["ip addr show ens3 | grep 'inet ' | awk '{print $2}' | cut -f1 -d'/'"],shell = True, stdout=subprocess.PIPE)
stdout = process.communicate()[0]
print('IP:{}'.format(stdout))




