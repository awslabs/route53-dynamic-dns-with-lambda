#!/bin/bash

#Get aguments
while getopts ":u:m:h:s:" opt; do
  case $opt in
    u) url="$OPTARG"
    ;;
    m) mode="$OPTARG"
    ;;
    h) host="$OPTARG"
    ;;
    s) secret="$OPTARG"
    ;;
    \?) echo "Invalid option -$OPTARG" >&2
    exit 1
    ;;
  esac

  case $OPTARG in
    -*) echo "Option $opt needs a valid argument"
    exit 1
    ;;
  esac
done

# Call the Lambda URL in get mode to get the IP address
function getip {
    #Evaluate -u argument
    if [ -z "$url" ]; then
        echo "Lambda url is required, pass it with argument -u, i.e. $0 -u https://xyz.lambda-url.eu-west1.on.aws/"
        exit 1
    fi
    
    #Get IP
    ip=`curl --ipv4 -q -s -X POST -H 'content-type: application/json' -d '{"execution_mode":"get"}' $url | egrep -o '[0-9\.]+'`
    
    #Return error
    if [ -z $ip ]; then
        echo "Cannot retrieve IP, check your Lambda URL is responding"
        exit 1
    fi
}

#Check execution mode
if [ $mode = "get" ]; then
    getip
    echo $ip
    exit 0
elif [ $mode = "set" ]; then
    #Evaluate secret and host argument
    if [ -z "$host" ]; then
        echo "Host argument -h is required when in set mode, i.e. $0 -h test.aws.com -m set  -s SHARED_SECRET_1 -u https://xyz.lambda-url.eu-west1.on.aws/"
    fi
    if [ -z "$secret" ]; then
        echo "Shared secret argument -s is required when in set mode, i.e. $0 -h test.aws.com -m set -s SHARED_SECRET_1 -u https://xyz.lambda-url.eu-west1.on.aws/"
    fi
    if [ -z "$host" ] | [ -z "$secret" ]; then
        exit 1
    fi    
    getip
    #Create hash
    hash=`echo -n $ip$host$secret | shasum -a 256 | awk '{print $1}'`
    #Call lambda url
    curl --ipv4 -s -X POST -w ",{\"status_code\":\"%{http_code}\"}" -H 'content-type: application/json' -d '{"execution_mode":"'$mode'", "ddns_hostname":"'$host'", "validation_hash":"'$hash'"}' $url
else
     echo "Mode is required as 'get' or 'set', pass it with argument -m, i.e. $0 -m get -u https://xyz.lambda-url.eu-west1.on.aws/"
     exit 1
fi