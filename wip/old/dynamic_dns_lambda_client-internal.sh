#!/bin/bash
# call script as:
# ./dynamic_dns_lambda_client.sh host1.dyn.example.com. SHARED_SECRET_1 "abc123.execute-api.us-west-2.amazonaws.com/prod"

# If the script is called with no arguments, show an instructional error message.
if [ $# -eq 0 ]
    then
    /bin/echo 'The script requires hostname and shared secret arguments.'
    /bin/echo "ie  $0 host1.dyn.example.com. sharedsecret \"abc123.execute-api.us-west-2.amazonaws.com/prod\""
    exit
fi

# Set variables based on input arguments
myHostname=$1
mySharedSecret=$2
myAPIURL=$3
internalExternal=$4
# Call the API in get mode to get the IP address
myIP=`/usr/bin/curl -q -s  "https://$myAPIURL?mode=get" | egrep -o '[0-9\.]+'`
/bin/echo $myIP

if [ ! -z $internalExternal ] && [ $internalExternal = internal ] ; then
	#Linux 
	#myWiredIP=`/sbin/ifconfig eth0 |egrep -o 'inet addr\:[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+' |awk -F ':' '{print $2}'`
	# OSX
	myWiredIP=`/sbin/ifconfig en0 |egrep -o 'inet\ [0-9]+\.[0-9]+\.[0-9]+\.[0-9]+' |awk -F ' ' '{print $2}'`
	/bin/echo $myWiredIP
	#myWifiIP=`/sbin/ifconfig wlan0 |egrep -o 'inet addr\:[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+' |awk -F ':' '{print $2}'`
	/bin/echo $myWifiIP
	if [ ! -z $myWiredIP ] && [[ $myWiredIP != 169* ]] ; then
	  myInternalIP=$myWiredIP
	elif [ ! -z $myWifiIP ]; then
	  myInternalIP=$myWifiIP
	else
	  /bin/echo "no address"
	fi
	/bin/echo $myInternalIP
	# Build the hashed token
	myHash=`/bin/echo -n $myIP$myHostname$mySharedSecret | /usr/bin/shasum -a 256 | /usr/bin/awk '{print $1}'`
	/usr/bin/curl -q -s "https://$myAPIURL?mode=set&hostname=$myHostname&hash=$myHash&internalIp=$myInternalIP"
else
	myHash=`/bin/echo -n $myIP$myHostname$mySharedSecret | /usr/bin/shasum -a 256 | /usr/bin/awk '{print $1}'`
	# Call the API in set mode to update Route 53
	/usr/bin/curl -q -s "https://$myAPIURL?mode=set&hostname=$myHostname&hash=$myHash"
fi
echo