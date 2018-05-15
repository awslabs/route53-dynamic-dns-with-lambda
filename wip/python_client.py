#!/usr/local/bin/python

import sys
import netifaces
import netaddr

def print_instructions():
	instructions = """
--------------------------------------------------------------------------------
The script supports the follwing arguments:
- Display local interface info: "discover"
- API endpoint url: "api=https://api.example.com" 
- API shared secret: "pass=shared_secret"
- selected interface as shown in ifconfig: "int=en0"
- dns record type: "record=public" - sets the public ipv4 address A record
                   "record=private" - sets the private ipv4 address A record
                   "record=ipv6" - sets the ipv6 AAAA record
- Set an SRV record as well:  "srv=8888"
- Optional: address number for interfaces that have multiple addresses
Example:
%s https://api.example.com en0 ipv4 1 
--------------------------------------------------------------------------------
"""
	print instructions % (sys.argv[0])

## Print instructions if no arguments are passed
if len(sys.argv) == 1:
	print_instructions()
	exit()

#if len(sys.argv) == 1:

script_verb = sys.argv[1]
selected_interface = sys.argv[2]
ip_version = sys.argv[3]
if len(sys.argv) < 4:
  address_number = 0
else:
  address_number = int(sys.argv[3])

interface_list=(netifaces.interfaces())
print((interface_list))
print((interface_list)[2])

print(netifaces.ifaddresses(selected_interface))

print(netifaces.AF_LINK)

#print(addrs[netifaces.AF_LINK])

addrs = netifaces.ifaddresses(selected_interface)
print(addrs[netifaces.AF_INET])
print(type(addrs[netifaces.AF_INET]))


for address in addrs[netifaces.AF_INET]:
	print(type(address))
	print(address['addr'])
	print('foo')

print(len(addrs[netifaces.AF_INET]))
print(len(addrs[netifaces.AF_INET6]))
print((addrs[netifaces.AF_INET][0]['addr']))
print((addrs[netifaces.AF_INET6][address_number]['addr']))