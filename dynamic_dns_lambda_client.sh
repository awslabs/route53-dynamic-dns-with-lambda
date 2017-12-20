#!/bin/bash

CACHEFILE="/tmp/dynamic_dns_lambda_client.tmp"

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
        Hostname to update. Example: "host1.dyn.example.com.".
        Mind the trailing dot.
        Required argument.

    --secret SECRET
        Secret to use when validating the request for the hostname.
        Required argument.

    --URL API_URL
        The URL where to send the requests.
        Required argument.

    --ip-source public | IP | INTERFACE
        This arguments defines how to get the IP we update to.
        public    - use the public IP of the device
        IP        - use a specific IP passed as argument
        INTERFACE - use the IP of an interface passed as argument

    --cache
        Store a cache file in $CACHEFILE.
        Whenever invoked, if the IP we want to update to is already cached, save some
        requests and stop.

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
        --host)
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
            myAPIURL=$2
            shift
            ;;
        --ip-source)
            if [ -z "$2" ] ; then
                fail "\"$1\" argument needs a value."
            fi
            sourceIP=$2
            shift
            ;;
        --cache)
            cache=true
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

if [ "$sourceIP" = "public" ]; then
    # Call the API in get mode to get the IP address
    myIP=$(curl -q -s  "https://$myAPIURL?mode=get" | jq -r '.return_message //empty')
    [ -z "$myIP" ] && fail "Couldn't find your public IP"
elif [[ $sourceIP =~ ^[0-9a-z]+$ ]]; then
    # IP - interface
    myIP="$(ip addr list "$sourceIP" |grep "inet " |cut -d' ' -f6|cut -d/ -f1)"
    [ -z "$myIP" ] && fail "Couldn't get the IP of $sourceIP."
elif [[ "$sourceIP" =~ ^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$ ]]; then
    myIP="$sourceIP"
else
    fail "Invalid --ip-source argument. Check help."
fi

if [ "$cache" = "true" ] && [ -f "$CACHEFILE" ]; then
    cached_myHostname=$(cat $CACHEFILE | cut -d'>' -f1)
    cached_myIP=$(cat $CACHEFILE | cut -d'>' -f2)
    if [ "$cached_myIP" = "$myIP" ] && [ "$cached_myHostname" = "$myHostname" ]; then
        echo "$(basename $0): Found a cached update."
        exit 0
    fi
fi

echo "$(basename $0): Updating $myHostname to IP $myIP."

# Build the hashed token
myHash=$(echo -n "$myIP$myHostname$mySharedSecret" | shasum -a 256 | awk '{print $1}')

# Call the API in set mode to update Route 53
if [ "$sourceIP" = "public" ]; then
    reply=$(curl -q -s "https://$myAPIURL?mode=set&hostname=$myHostname&hash=$myHash")
else
    reply=$(curl -q -s "https://$myAPIURL?mode=set&hostname=$myHostname&hash=$myHash&localIp=$myIP")
fi

if [ "$(echo "$reply" | jq -r '.return_status //empty')" == "success" ]; then
    if [ "$cache" = "true" ]; then
        echo "$myHostname>$myIP" > $CACHEFILE
    fi
    echo -n "$(basename $0): Request succeeded: "
else
    echo -n "$(basename $0): Request failed: "
fi
echo "$(echo "$reply" | jq -r '.return_message //empty')"
