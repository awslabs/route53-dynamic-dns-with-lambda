#!/bin/bash

# Wrapper script to discover ip addresses on the same network segment and set dns.
# Call this script as you would the main route53-ddns-client.sh script
# ./network-discovery.sh --hostname test.example.com --secret XXX --url ddns.example.com --ip-version ipv4/6
# Note that the hostname called 'test.example.com' is used for authentication.
# To set dns for that host, call the main route53-ddns-client.sh directly
# Call the script separately for ipv4 and ipv6

## requires jq - available via most Linux package managers and Brew on OSX

# Set route53-ddns-client.sh path
route53DdnsClient="./route53-ddns-client.sh"
# Set default ipVersion
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

if [ "$ipVersion" = "ipv4" ]; then
    searchRecordType="A"
    netScan=$(arp -a| awk '{print $2 " " $4}'|sed 's|[(),]||g')
elif [ "$ipVersion" = "ipv6" ]; then
    searchRecordType="AAAA"
    ## Check for either ip or ndp for ipv6 network discovery.
    if command -v ip > /dev/null 2>&1 ; then
        netScan=$(ip -6 neigh |egrep -v fe80 | awk '{print $1 " " $5}')
    elif command -v ndp > /dev/null 2>&1 ; then
        netScan=$(ndp -a |egrep -v fe80 | awk '{print $1 " " $2}')
    fi
fi

response=$($route53DdnsClient --hostname $myHostname --secret $mySharedSecret --api-key $apiKey --url $myAPIURL --list-hosts)
hostList=$(echo $response |egrep -o '\[.*')
hostCount=$(echo $hostList | jq '.| length')
 
for ((i=0; i<hostCount; i++)); do
    recordType=$(echo $hostList | jq -r --argjson recordId $i '.[$recordId].record_type')
    if [ "$recordType" = "$searchRecordType" ]; then
        macAddress=$(echo $hostList | jq -r --argjson recordId $i '.[$recordId].mac_address')
        setIp=$(echo "$netScan"|egrep -i $macAddress |awk '{print $1}')
        if [[ ! -z $setIp ]] ; then
            ## ipv6 can return multiple addresses, we need only one
            setIp=(${setIp[0]})
            hostName=$(echo $hostList | jq -r --argjson recordId $i '.[$recordId].hostname')
            if [ "$myHostname" != "$hostName" ]; then
                setResponse=$($route53DdnsClient --hostname $hostName --secret $mySharedSecret --api-key $apiKey --url $myAPIURL  --ip-source $setIp --ip-version $ipVersion)
                echo $setResponse
                echo
            fi
        fi
    fi
done
