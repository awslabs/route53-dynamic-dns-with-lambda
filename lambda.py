import requests
import hashlib

# set variables
hostname = 'host1.dyn.example.com.'
secret = 'sharedsecret'
apiurl = 'abc123.execute-api.us-west-2.amazonaws.com/prod'
# call the api in get mode and save the ip return value
r = requests.get(apiurl, params={'mode': 'get'})
ip = r.json()['return_message']
# build the hashed token
hash = hashlib.sha256(str.encode(ip+hostname+secret)).hexdigest()
# call the api in set mode to update route 53
r = requests.get(apiurl, params={'mode': 'set', 'hostname': hostname, 'hash': hash})