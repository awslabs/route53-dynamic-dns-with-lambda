#!/bin/bash

## Implements setting internal IP with --ip-source
## and --cache
## The api_mapping_template and dynamic_dns_lambda.py
## have been updated to support setting internal IP.
## Note that this weakens the security of the system since the client specifies
## the IP to set, where before the IP was set to the source IP of the client request.
## This client will work against the previous versions of the API without the internal IP feature.


## Cache file settings
## cacheFileDir must end in /
## Recommend /tmp/ddns_cache/ to clear cache on restart
cacheFileDir="/tmp/ddns_cache/" 
cacheFileExt="ddns.tmp"

fail () {
    echo "$(basename $0): $1"
    exit 1
}

help () {
    cat << EOF
Set the IP for a specific hostname on route53
dynamic_dns_lambda_client.sh [options]

Options:
    -h, --help
        Display this help and exit.
    --hostname HOSTNAME
        Hostname to update. Example: "host1.dyn.example.com."
        Mind the trailing dot.
        Required argument.
    --secret SECRET
        Secret to use when validating the request for the hostname.
        Required argument.
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
            myHostname=$2
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
        	#fail "\"$1\" Currently not implemented."
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
            	if [ ! -d $cacheFileDir ]; then mkdir $cacheFileDir ; fi
            else
				fail "\"$1\" argument must be an integer reflecting ttl in minutes."
            fi
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

cacheFile="$cacheFileDir$myHostname$cacheFileExt"
## get public IP from reflector to generate hash &/or set IP
myPublicIP=$(curl -q -s  "$myAPIURL?mode=get" | jq -r '.return_message //empty')

if [ "$ipSource" = "public" ] || [ -z "$ipSource" ]; then
    # Call the API in get mode to get the IP address
    #myIP=$(curl -q -s  "$myAPIURL?mode=get" | jq -r '.return_message //empty')
    myIP=$myPublicIP
    [ -z "$myIP" ] && fail "Couldn't find your public IP"
## match interface formats eth0 eth0:1 eth0.1
elif [[ $ipSource =~ ^[0-9a-z]+([:.][0-9]+){0,1}$ ]]; then
    myIP="$(ifconfig "$ipSource" |egrep 'inet\ '|egrep -o '((1?[0-9][0-9]?|2[0-4][0-9]|25[0-5])\.){3}(1?[0-9][0-9]?|2[0-4][0-9]|25[0-5])' |head -1)"
    [ -z "$myIP" ] && fail "Couldn't get the IP of $ipSource."
elif [[ "$ipSource" =~ ^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$ ]]; then
    myIP="$ipSource"
else
    fail "Invalid --ip-source argument. Check help."
fi
if [ "$cache" = "true" ] && [ -f "$cacheFile" ] && [ `find $cacheFile -mtime -"$cacheTtl"m | grep '.*'` ]; then
    cached_myIP=$(cat $cacheFile)
    if [ "$cached_myIP" = "$myIP" ]; then
        echo "$(basename $0): Found a cached update."
        exit 0
    fi
fi

echo "$(basename $0): Updating $myHostname to IP $myIP."

# Build the hashed token
if command -v shasum > /dev/null 2>&1 ; then
	myHash=$(echo -n "$myPublicIP$myHostname$mySharedSecret" | shasum -a 256 | awk '{print $1}')
elif command -v sha256sum  > /dev/null 2>&1 ; then
	myHash=$(echo -n "$myPublicIP$myHostname$mySharedSecret" | sha256sum | awk '{print $1}')
else
	fail "Neither shasum nor sha256sum binaries were found on host"
fi

# Call the API in set mode to update Route 53
if [ "$ipSource" = "public" ]; then
    reply=$(curl -q -s "$myAPIURL?mode=set&hostname=$myHostname&hash=$myHash")
else
    reply=$(curl -q -s "$myAPIURL?mode=set&hostname=$myHostname&hash=$myHash&internalIp=$myIP")
fi

if [ "$(echo "$reply" | jq -r '.return_status //empty')" == "success" ]; then
    if [ "$cache" = "true" ]; then
        echo "$myIP" > $cacheFile
    fi
    echo "$(basename $0): Request succeeded: $(echo "$reply" | jq -r '.return_message //empty')"
else
    echo "$(basename $0): Request failed: $(echo "$reply" | jq -r '.return_message //empty')"
    exit 1
fi

