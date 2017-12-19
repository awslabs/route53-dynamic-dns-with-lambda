#!/bin/bash
# call script as:
# ./dynamic_dns_lambda_client.sh host1.dyn.example.com. SHARED_SECRET_1 "abc123.execute-api.us-west-2.amazonaws.com/prod"

fail () {
    echo "FAIL: $1"
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

    --interface INTERFACE
        By default the tool updates the hostname with the public IP. This arguments forces
        the update to use the IP of a specific interface.
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
            # Argument needs to be non-empty and absolute path
            if [ -z "$2" ] ; then
                fail "\"$1\" argument needs a value."
            fi
            myAPIURL=$2
            shift
            ;;
        --interface)
            # Argument needs to be non-empty and absolute path
            if [ -z "$2" ] ; then
                fail "\"$1\" argument needs a value."
            fi
            interface=$2
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
    echo 'The script requires hostname and shared secret arguments.'
    echo "ie  $0 host1.dyn.example.com. sharedsecret \"abc123.execute-api.us-west-2.amazonaws.com/prod\""
    exit
fi

if [ -z "$interface" ]; then
    # Call the API in get mode to get the IP address
    myIP=$(curl -q -s  "https://$myAPIURL?mode=get" | jq -r '.return_message //empty')
    [ -z "$myIP" ] && fail "Couldn't find your public IP"
else
    # Use the ip address of a specific interface
    myIP="$(ip addr list "$interface" |grep "inet " |cut -d' ' -f6|cut -d/ -f1)"
    [ -z "$myIP" ] && fail "Couldn't get the IP of $interface."
fi

echo "Updating $myHostname to IP $myIP."

# Build the hashed token
myHash=$(echo -n "$myIP$myHostname$mySharedSecret" | shasum -a 256 | awk '{print $1}')

# Call the API in set mode to update Route 53
if [ -z $interface ]; then
    reply=$(curl -q -s "https://$myAPIURL?mode=set&hostname=$myHostname&hash=$myHash")
else
    reply=$(curl -q -s "https://$myAPIURL?mode=set&hostname=$myHostname&hash=$myHash&localIp=$myIP")
fi

if [ "$(echo "$reply" | jq -r '.return_status //empty')" == "success" ]; then
    echo -n "Request succeeded: "
else
    echo -n "Request failed: "
fi
echo "$(echo "$reply" | jq -r '.return_message //empty')"
