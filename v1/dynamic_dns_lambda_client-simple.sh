#!/bin/bash
# call script as:
# ./dynamic_dns_lambda_client.sh host1.dyn.example.com. SHARED_SECRET_1 "abc123.execute-api.us-west-2.amazonaws.com/prod"

# If the script is called with no arguments, show an instructional error message.
if [ $# -eq 0 ]
    then
    echo 'The script requires hostname and shared secret arguments.'
    echo "ie  $0 host1.dyn.example.com. sharedsecret \"abc123.execute-api.us-west-2.amazonaws.com/prod\""
    exit
fi

# Set variables based on input arguments
myHostname=$1
mySharedSecret=$2
myAPIURL=$3
# Call the API in get mode to get the IP address
myIP=`curl -q -s  "https://$myAPIURL?mode=get" | egrep -o '[0-9\.]+'`
# Build the hashed token
myHash=`echo -n $myIP$myHostname$mySharedSecret | shasum -a 256 | awk '{print $1}'`
# Call the API in set mode to update Route 53
curl -q -s "https://$myAPIURL?mode=set&hostname=$myHostname&hash=$myHash"
echo