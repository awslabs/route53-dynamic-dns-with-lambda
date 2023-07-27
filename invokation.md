# Invokation

The Lambda function will be invoked with a **POST** request to the Function URL.

The function can be invoked to **GET** or **SET** an IPV4 address.

### GET the IP address

To **GET** the public IP address issue a post request with the following JSON object in the body:
```JSON
{"execution_mode":"get"}
```

Here an example invokation with *CURL*:<br>
> ` 
curl --ipv4 -q -s -X POST -H 'content-type: application/json' -d '{"execution_mode":"get"}' https://1234567890xyz.lambda-url.eu-west-1.on.aws/
`

The function will return the following **JSON** Object with a `200 HTTP Status code`:
```JSON
{"return_status": "success", "return_message": "11.12.13.14"}
```
To isolate the IP address in the reponse you can pipe:
>` egrep -o '[0-9\.]+' `

For exampple:
>`curl --ipv4 -q -s -X POST -H 'content-type: application/json' -d '{"execution_mode":"get"}' https://1234567890xyz.lambda-url.eu-west-1.on.aws/ | egrep -o '[0-9\.]+'`

Only the IP address will be returned:
> `11.12.13.14`

### SET the IP address
Once the public IP is obtained the function can be invoked to **SET** the DNS record.\
This JSON Object must be posted to **SET**:
```JSON
{"execution_mode":"set", "ddns_hostname":"'www.example.com'", "validation_hash":"'1234567890ABCDEFGH'"}
```
The Lambda function will validate the hash that is genereated by concatenating the following parameters:
* Public IP
* hostname
* shared secret

and hashing the reuslting string with:
>`shasum -a 256`

To store the hash in a variable pipe the following:
>`awk '{print $1}'`

For example:
>`echo -n 11.12.13.14www.example.comSuP3R_5eCR3T | shasum -a 256 | awk '{print $1}'`

will return:
> `0eb3fc760ddbd7dca1702ae359b8f990b8a145d719b9d1014da4aa866022dd70`

### dyndns.sh bash script

In this repository is included a bash script: [dyndsn.sh](dyndns.sh) to programmatically invoke the Lambda function using **CURL**

When using [newrecord.py](newrecord.py) script to create the configuration, all the flags will be provided to run [dyndns.sh](dyndns.sh), i.e.:
> ` ./dyndns.sh -m set -u https://1234567890xyz.lambda-url.eu-west-1.on.aws/ -h www.example.com -s SuP3R_5eCR3T `

#### Script flags
* MODE: **-m** *(required)*\
This can be **get** to obtain the public IP or **set** to update the DNS record.

* URL: **-u** *(required)*\
The Lambda Function URL, i.e.: *https://1234567890xyz.lambda-url.eu-west-1.on.aws/*

* HOST: **-h** *(required if **-m set**)*\
The hostname which needs to be updated, i.e.: *www.example.com*

* SECRET: **-s** *(requried if **-m set)***\
The shared secret provided in the DynamoDB configuration, i.e.: *SuP3R_5eCR3T*

#### GET example
>`./dyndns.sh -m get -u https://1234567890xyz.lambda-url.eu-west-1.on.aws/ `

It will return the Public IP address:
>`11.12.13.14`

#### SET example
>`./dyndns.sh -m set -u https://1234567890xyz.lambda-url.eu-west-1.on.aws/ -h www.example.com -s SuP3R_5eCR3T`

It will return the following if successful:
```JSON
{"return_status": "success", "return_message": "www.example.com has been updated to 11.12.13.14"},{"status_code":"201"}
```

If the hostname already matches the public IP it will returm:
```JSON
{"return_status": "success", "return_message": "Your IP address matches the current Route53 DNS record."},{"status_code":"200"}
```

## **Failed requests examples and troubleshooting**
\
` HTTP 403 Status code`
>***There was an issue finding or reading www.example.com configuration from dynamoDB table: DyndnsStack-***
```JSON
{"return_status": "fail", "return_message": "There was an issue finding or reading www.example.com configuration from dynamoDB table: DyndnsStack-dyndnsdb12345-ABC0000"},{"status_code":"403"}
```
* **Validate the DynamoDB configuration**\
Is the configuration present for "www.example.com"?\
Is the *hostname* atribute typed correctly?\
Does the *data* attribute contain a valid **JSON** configuration (i.e. [www.example.com.json](www.example.com.json)) ?

`HTTP 400 Status code`
>***You must pass a valid sha256 hash in the hash= argument***
```JSON
{"return_status": "fail", "return_message": "You must pass a valid sha256 hash in the hash= argument."}
```
* Ensure **shasum** is present on the system and used correctly to generate the hash.

`HTTP 401 Status code`
>***Validation hashes do not match***

Ensure the hash is generated using a string containining:
* The correct public IP address returned by *./dyndsn.sh -m get*
* The correct host, i.e.: *www.example.com*
* A string matching the *shared_secret* JSON parameter in the **data** attribute in DynamoDB
* Ensure the hashed string had the 3 parameters in the right order: IP HOST SECRET\
i.e.: *11.12.13.14www.example.comSuP3R_5eCR3T*

***Internal Server Errors***

`HTTP 502 Status code`
>***Internal Server Error***

This will be returned when there is an unexpected exception within the Lambda function.<br>
Review [Amazon CloudWatch](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/WhatIsCloudWatch.html) Log Groups for troubleshooting and consider opening an issue on this repository.

`HTTP 501 Status code`
>***An error occurred (InvalidChangeBatch) when calling the ChangeResourceRecordSets operation: [RRSet of type A with DNS name www.example.com. is not permitted because [ROUTE53 ERROR MESSAGE]***

This error occurs when `www.example.com` recordset already exist but is not type `A`<br>
Remove the unwanted record or use a different hostname.<br>
A new configuration can be created using [newrecord.py](newrecord.py)

`HTTP 500 Status code`
>***An error occurred (NoSuchHostedZone) when calling the ListResourceRecordSets operation: No hosted zone found with ID: Z123456ABABO1ABC10A***

The Host Zone ID (i.e. `Z123456ABABO1ABC10A`) is incorrect, if the Hosted Zone ID doesn't exist, create it, if it exists verify that the Hosted Zone ID is correctly saved in the DynamoDB configuration.<br>
A new configuration can be created using [newrecord.py](newrecord.py)

HTTP Status code `500` will be returned for any other Route53 exception, refer to `"return_message"` in the reposnse body for more information on the error:
```json
{"return_status": "fail", "return_message": "[ROUTE53 Error Message]"}
```