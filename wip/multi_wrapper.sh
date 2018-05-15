#!/bin/bash

## Implements setting internal IP with --ip-source
## and --cache
## The api_mapping_template and dynamic_dns_lambda.py
## have been updated to support setting internal IP.
## Note that this weakens the security of the system since the client specifies
## the IP to set, where before the IP was set to the source IP of the client request.
## This client will work against the previous versions of the API without the internal IP feature.

## Tested on:
## Mac OSX 10.11, 10.12 & 10.13
## Ubuntu 16.04
## Amazon Linux & Amazon Linux 2
## Tomato USB Router

## requires jq - available via most Linux package managers and Brew on OSX


## Set default to ipv4, can be overridden by --ip-version
ipVersion="ipv4"

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
        Hostname requires the trailing '.' in request and the DDB config table entry.
        Required argument.
    --secret SECRET
        Secret to use when validating the request for the hostname.
        Required argument.
    --url API_URL
        The URL where to send the requests.
        Required argument.
    --ip-version ipv4 | ipv6
    	If called, requires an argument.
    	Assumes ipv4 if omitted.
    --api-key
        Pass the Amazon API Gateway API Key
        Not currently implemented in API
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
        --ip-version)
            if [ -z "$2" ] ; then
                fail "\"$1\" argument needs a value."
            fi
			ipVersion=$2
            shift
            ;;
        --api-key)
            if [ -z "$2" ] ; then
                fail "\"$1\" argument needs a value."
            fi
			apiHeader="x-api-key: $2"
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
myPublicIP=$(curl -q --$ipVersion -s  -H "$apiHeader" "$myAPIURL?mode=get" | jq -r '.return_message //empty')

## Build the hashed token
## Check for shasum (OSX) vs sha256sum (Linux) then execute the appropriate command.
if command -v shasum > /dev/null 2>&1 ; then
	myHash=$(echo -n "$myPublicIP$myHostname$mySharedSecret" | shasum -a 256 | awk '{print $1}')
elif command -v sha256sum  > /dev/null 2>&1 ; then
	myHash=$(echo -n "$myPublicIP$myHostname$mySharedSecret" | sha256sum | awk '{print $1}')
else
	fail "Neither shasum nor sha256sum executables were found on host."
fi

reply=$(curl -q --$ipVersion -s -H "$apiHeader" "$myAPIURL?mode=list_hosts&hostname=$myHostname&hash=$myHash")

if [ "$(echo "$reply" | jq -r '.return_status //empty')" == "success" ]; then
    echo "$(basename $0): Request succeeded: $(echo "$reply"| jq -r '.return_message //empty')"
else
    echo "$(basename $0): Request failed: $(echo "$reply" | jq -r '.return_message //empty')"
    exit 1
fi
#echo $reply
