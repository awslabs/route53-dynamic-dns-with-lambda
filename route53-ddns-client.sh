#!/bin/bash

## Tested on:
## Mac OSX 10.11, 10.12 & 10.13
## Ubuntu 16.04
## Amazon Linux & Amazon Linux 2
## Tomato USB Router

## requires jq - available via most Linux package managers, Brew on OSX
## and binaries or source at https://stedolan.github.io/jq/download/

## Cache file settings
## cacheFileDir must end in /
## Recommend /tmp/ddns_cache/ to clear cache on restart
cacheFileDir="/tmp/ddns_cache/" 
cacheFileExt=".ddns.tmp"
## Set default to ipv4, can be overridden by --ip-version
ipVersion="ipv4"

fail () {
    echo "$(basename $0): $1"
    exit 1
}

help () {
    cat << EOF
Set the IP for a specific hostname on route53
route53-ddns-client.sh [options]

Options:
    -h, --help
        Display this help and exit.
    --hostname HOSTNAME
        Hostname to update. Example: "host1.dyn.example.com."
        Hostname requires the trailing '.' in request and the DDB config table entry.
        Required argument.
    --secret SECRET
        Secret to use when validating the request for the hostname. This is referred to in the documentation as the Shared Secret.
        Required argument.
    --api-key
        Pass the Amazon API Gateway API Key
    --url API_URL
        The URL where to send the requests.
        Required argument.
    --ip-source public | IP | INTERFACE
        This arguments defines how to get the IP we update to.
        public    - use the public IP of the device (default)
        IP        - use a specific IP passed as argument
        INTERFACE - use the IP of an interface passed as argument eg: eth0 eth0.1 or eth0:1
    --cache CACHE_TTL_MINUTES
        Stores a cache file in $cacheFileDir
        Whenever invoked, if the IP we want to update to is already cached, save some
        requests and stop. (Note that this will only save significant cost at scale)
        TTL is used to invalidate cache.
        If omitted, caching is disabled.
    --ip-version ipv4 | ipv6
    	If called, requires an argument.
    	Assumes ipv4 if omitted.
    --list-hosts
        List hosts from DynamoDB that belong to the same group as the calling host.
        Hosts are grouped by shared secret.
        Not yet fully implemented.  Will allow a single host to set records for all hosts on
        a network segment.
        Not required.
        No argument.	
EOF
}

# Parse arguments
while [[ $# -ge 1 ]]; do
    i="$1"
    case $i in
        -h|--help)
            help
            exit 0
            ;;
        --hostname)
            if [ -z "$2" ]; then
                fail "\"$1\" argument needs a value."
            fi
            if [[ "$2" == *. ]]; then
                myHostname=$2
            else
                ## add trailing . if omitted
                myHostname=$2
                myHostname+='.'
            fi
            shift
            ;;
        --secret)
            if [ -z "$2" ]; then
                fail "\"$1\" argument needs a value."
            fi
            mySharedSecret=$2
            shift
            ;;
        --url)
            if [ -z "$2" ] ; then
                fail "\"$1\" argument needs a value."
            fi
            if [[ "$2" == "https://"* ]]; then
            	myAPIURL=$2
            else
            	myAPIURL="https://"$2
            fi
            shift
            ;;
        --ip-source)
            if [ -z "$2" ] ; then
                fail "\"$1\" argument needs a value."
            fi
            ipSource=$2
            shift
            ;;
        --cache)
            if [ -z "$2" ] ; then
                fail "\"$1\" argument needs a value."
            fi
            if [[ $2 =~ [0-9]+ ]]; then
				cacheTtl=$2
				cache=true
            	if [ ! -d $cacheFileDir ]; then mkdir -p $cacheFileDir ; fi
            else
				fail "\"$1\" argument must be an integer reflecting ttl in minutes."
            fi
            shift
            ;;
        --ip-version)
            if [ -z "$2" ] ; then
                fail "\"$1\" argument needs a value."
            fi
			ipVersion=$2
            shift
            ;;
        --list-hosts)
			listHosts=true
            shift
            ;;
        --api-key)
            if [ -z "$2" ] ; then
                fail "\"$1\" argument needs a value."
            fi
			apiKey="$2"
            shift
            ;;
        *)
            fail "Unrecognized option $1."
            ;;
    esac
    shift
done

# If the script is called with no arguments, show an instructional error message.
if [ -z "$myHostname" ] || [ -z "$mySharedSecret" ] || [ -z "$myAPIURL" ]; then
    echo "$(basename $0): Required arguments missing."
    help
    exit 1
fi

cacheFile="$cacheFileDir$myHostname$ipVersion$cacheFileExt"

## get public IP from reflector to generate hash &/or set IP
myPublicIP=$(curl -q --$ipVersion -s  -H "x-api-key: $apiKey" "$myAPIURL?mode=get" | jq -r '.return_message //empty')

if [ "$ipSource" = "public" ] || [ -z "$ipSource" ]; then
    myIp=$myPublicIP
    [ -z "$myIp" ] && fail "Couldn't find your public IP"
## match interface formats eth0 eth0:1 eth0.1
elif [[ $ipSource =~ ^[0-9a-z]+([:.][0-9]+){0,2}$ ]]; then
	if [ "$ipVersion" = "ipv4" ]; then
    	myIp="$(ifconfig "$ipSource" |egrep 'inet\ '|egrep -o '((1?[0-9][0-9]?|2[0-4][0-9]|25[0-5])\.){3}(1?[0-9][0-9]?|2[0-4][0-9]|25[0-5])' |head -1)"
    	[ -z "$myIp" ] && fail "Couldn't get the IP of $ipSource"
	elif [ "$ipVersion" == "ipv6" ]; then
    	myIp="$(ifconfig "$ipSource" |egrep 'inet6' |egrep -v 'fe80'|egrep -v 'temporary'|egrep -io '([A-F0-9]{1,4}:){7}[A-F0-9]{1,4}')"
		[ -z "$myIp" ] && fail "Couldn't get the IP of $ipSource"
    else
    	fail "Interface source called, but ipVersion is not set." ## This should never happen.  Defaults set to ipv4 at top of script
    fi
## match ipv4
elif [[ "$ipSource" =~ ^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$ ]]; then
    myIp="$ipSource"
## match ipv6
elif [[ "$ipSource" =~ ^[0-9A-Fa-f:]+$ ]]; then
	myIp="$ipSource"
else
    fail "Invalid --ip-source argument. Check help."
fi
if [ "$cache" = "true" ] && [ -f "$cacheFile" ] && [ `find $cacheFile -mmin -"$cacheTtl" | grep '.*'` ]; then
    cached_myIp=$(cat $cacheFile)
    if [ "$cached_myIp" = "$myIp" ]; then
        echo "$(basename $0): Found a cached update."
        exit 0
    fi
fi

echo "$(basename $0): Updating $myHostname to IP $myIp"

## Build the hashed token
## Check for shasum (OSX) vs sha256sum (Linux) then execute the appropriate command.
if command -v shasum > /dev/null 2>&1 ; then
	myHash=$(printf "$myPublicIP$myHostname$mySharedSecret" | shasum -a 256 | awk '{print $1}')
elif command -v sha256sum  > /dev/null 2>&1 ; then
	myHash=$(printf "$myPublicIP$myHostname$mySharedSecret" | sha256sum | awk '{print $1}')
else
	fail "Neither shasum nor sha256sum executables were found on host."
fi

if [ "$listHosts" = "true" ]; then
    reply=$(curl -q --$ipVersion -s -H "x-api-key: $apiKey" "$myAPIURL?mode=list_hosts&hostname=$myHostname&hash=$myHash")
# Call the API in set mode to update Route 53
elif [ "$listHosts" != "true" ] && [ "$ipSource" = "public" ]; then
    reply=$(curl -q --$ipVersion -s -H "x-api-key: $apiKey" "$myAPIURL?mode=set&hostname=$myHostname&hash=$myHash")
else
    reply=$(curl -q --$ipVersion -s -H "x-api-key: $apiKey" "$myAPIURL?mode=set&hostname=$myHostname&hash=$myHash&internalIp=$myIp")
fi

if [ "$(echo "$reply" | jq -r '.return_status //empty')" == "success" ]; then
    if [ "$cache" = "true" ]; then
        echo "$myIp" > $cacheFile
    fi
    echo "$(basename $0): Request succeeded: $(echo "$reply"| jq -r '.return_message //empty')"
else
    echo "$(basename $0): Request failed: $(echo "$reply" | jq -r '.return_message //empty')"
    exit 1
fi


