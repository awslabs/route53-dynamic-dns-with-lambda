# route53-dynamic-dns-with-lambda
### A Dynamic DNS system built with API Gateway, Lambda &amp; Route 53.  

*This repository originally supplemented the blog post: [Building a Serverless Dynamic DNS System with AWS](https://medium.com/aws-activate-startup-blog/building-a-serverless-dynamic-dns-system-with-aws-a32256f0a1d8)  
Code and instructions for the version described in the blog can be found in the [v1](./v1/)  folder of this repository.*   

The project implements a serverless dynamic DNS system using AWS Lambda, Amazon API Gateway, Amazon Route 53 and Amazon DynamoDB.   
A bash reference client *route53-ddns-client.sh* is included, but the api calls for the system can be easily implemented in other languages.  
The benefits and overall architecture of the system described in [Building a Serverless Dynamic DNS System with AWS](https://aws.amazon.com/blogs/startups/building-a-serverless-dynamic-dns-system-with-aws/) are still accurate.   

#### The current project supports:
- One step provisioning via AWS CloudFormation  
- System configuration in Amazon DynamoDB   
- ipv6 support   
- Internal ip address (rfc1918) support  
- Custom API endpoint hostname
- Network discovery: Enables a single host on a network segment to set DNS entries for multiple other hosts on the same network.

---
###### *Navigate* | [*Top*](#route53-dynamic-dns-with-lambda) | [*Setup*](#setup-guide) | [*Outputs*](#cloudformation-stack-outputs) | [*Configuration*](#configuration-guide) | [*Security*](#security-considerations) | [*Network Discovery*](#network-discovery) | [*API Reference*](#api-reference) |   
---
### Setup Guide 


#### Deploy the CloudFormation Template:
* Create an AWS CloudFormation stack using the provided template: *[route53-ddns.yml](/route53-ddns.yml)*
* To deploy via AWS Console (simplest): See [Upload a template to Amazon S3](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/cfn-using-console-create-stack-template.html)  
* To deploy via AWS CLI:  See [Creating a Stack](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-cli-creating-stack.html)  

#### Set the CloudFormation Stack parameters
* *Stack name*  - required   
All Stack resources are named using the CloudFormation Stack name you choose.  
Because of this, the Stack name must be compatible with the name restrictions of all services deployed by the stack.  
Only use lower case letters, numbers '_' and  '-'  

* *route53ZoneName* - required  
Route53 Zone name.  ie 'example.com'  
Use either existing zone or name of zone to be created by the stack.  
Zone name must not end in '.'  
If using an existing zone, *route53ZoneName* must match the name of the zone passed in *route53ZoneId*.  
For [Private Hosted Zones](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/hosted-zones-private.html), you must use an existing zone.  

All remaining parameters can be left blank or at defaults. 

* *route53ZoneId*  
Populate to use an existing zone. ie 'Z1FXLQ1OABKR4O'  
The zone must exist in the same account as the stack.  
If omitted, a new Route53 DNS zone will be created.  
If supplied, the ddns system will gain IAM permissions to modify existing zone entries.  

* *defaultTtl*  
The default TTL for DNS records, can be overridden for individual records in DynamoDB config.  

* *enableCloudFront*  
CloudFront is required for ipv6 support or to use a custom API Alias (CNAME).  
Note that the Stack creation will not complete until after the CloudFront distribution is done propagating. 
This adds several munites to Stack creation time.  
  -*false* - Call API Gateway directly  
  -*withCustomAlias* - Required for ipv6 and/or *apiCname*  
  -*withoutCustomAlias* - Required for ipv6 

* *apiCname*  
API Endpoint Custom Alias  
Required for *enableCloudFront withCustomAlias*  
Will create a CNAME to your API endpoint in the *route53ZoneName* supplied.  
i.e. entering 'ddns' for *route53ZoneName* 'example.com' will create the CNAME 'ddns.example.com'  

* *useApiKey*  
Adds an API Key to your API Gateway.  
Requests to the API without the proper key are blocked instead of passing through to Lambda.  
This prevents DOS/resource depletion attacks against your Lambda backend.  
The auto-generated key is published to the stack outputs.  

* *acmCertificateArn*  
Required to use a custom dns endpoint (Alias) for your API.  
Populate to use an existing ACM Certificate.  (CloudFormation will not create a certificate on your behalf.)   
Full ARN of an ACM SSL Certificate:  
i.e. 'arn:aws:acm:us-east-1:123456789012:certificate/a1aaab22-11ab-ab12-cd34-12345abc0ab0'  
The certificate must be in us-east-1 (Virginia) Region.  
The certificate can either match the API endpoint custom alias. i.e. 'ddns.example.com'  
or the entire zone i.e. '*.example.com'  
See: [Request a Public Certificate](https://docs.aws.amazon.com/acm/latest/userguide/gs-acm-request-public.html)  

* *CloudFrontPriceClass*  
Leave at default unless you are accessing from outside US, Canada & Europe.  
See [documentation.](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/PriceClass.html)  
    -US-Canada-Europe   
    -US-Canada-Europe-Asia  
    -All-Edge-Locations   

* *DynamoDB Configuration*  
Sets the provisioned capacity of the DynamnoDB table built by CloudFormation.   
*ddbRcu* & *ddbWcu* set the Read & Write capacity units for the DynamnoDB table.  
*ddbGsiRcu* & *ddbGsiWcu* set the Read & Write capacity units for the DynamnoDB Global Secondary Index.  
Leave at defaults for small scale deployments.  
Provisioned capacity affects both [scalability](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/ProvisionedThroughput.html#ProvisionedThroughput.Throttling) and [cost](https://aws.amazon.com/dynamodb/pricing/).  

* *templateVersion*  
Sometimes required to force a stack update or force Lambda-backed custom resources to run.   
The system does not actually track the version, if needed increment or simply change it to another arbitrary digit.  

###### *Navigate* | [*Top*](#route53-dynamic-dns-with-lambda) | [*Setup*](#setup-guide) | [*Outputs*](#cloudformation-stack-outputs) | [*Configuration*](#configuration-guide) | [*Security*](#security-considerations) | [*Network Discovery*](#network-discovery) | [*API Reference*](#api-reference) |   
---
### CloudFormation Stack Outputs  

When Stack creation is complete you may need to look at the [Outputs](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/cfn-console-view-stack-data-resources.html) 
for information necessary to proceed with setup.  

#### ddns Stack Outputs:  
* *apiUrl*  
Use this as your API endpoint  
It is a calculated output based on your Parameter choices.  
It will either reflect the API Gateway, CloudFront, or Custom Alias of the API.  

* *apiOriginURL*  
The API Gateway endpoint URL  

* *cloudFrontURL*  
The CloudFront endpoint URL  

* *route53ZoneID*  
* *route53ZoneName*  
* *DNSZoneNameServers*  
Name servers associated with your zone.  
If the Stack built a new Zone, use these to:  
[Associate the Zone](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/domain-name-servers-glue-records.html) with your registered Domain,    
or [delegate the zone as a subdomain](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/CreatingNewSubdomain.html#UpdateDNSParentDomain).  

* *apiKey*  
API Key generated by the stack.  Pass as argument to sample clients.  
To use in curl, pass as `-H 'x-api-key: myApikeyPastedFromOutputs'`  

###### *Navigate* | [*Top*](#route53-dynamic-dns-with-lambda) | [*Setup*](#setup-guide) | [*Outputs*](#cloudformation-stack-outputs) | [*Configuration*](#configuration-guide) | [*Security*](#security-considerations) | [*Network Discovery*](#network-discovery) | [*API Reference*](#api-reference) |   
---
### Configuration Guide     

The system creates a DynamoDB Table for configuration named *[stackName]-config*.  
You must create an Item (row) for each Route53 DNS entry managed by the system.  
The Table is pre-populated with two example Items to duplicate and modify.   
Note that some attributes are for configuration, while others (marked read-only below) reflect state information from the system.   

#### Configuration Table Attributes  
* *hostname*  
The hostname of the dns record.  

* *record_type*  
A for ipv4 or AAAA for ipv6 records  
Note that *hostname* and *record_type* form the composite primary key for the Table.  
The combination of the two Attributes in each Item must be unique.  

* *allow_internal*  
Boolean to control whether the record can be set to an internal (rfc1918) address  
See [Security Considerations](#security-considerations)  

* *comment*  
For your reference only, unused by ddns.

* *ip_address*  - read-only  
Reflects the last IP address set for the record by the ddns system 

* *last_accessed*  - read-only  
Reflects the last public IP address from which the record was read or modified   

* *last_checked*  - read-only  
Reflects the last time the record was read by the ddns system

* *last_updated*  - read-only  
Reflects the last time the record was modified by the ddns system  

* *lock_record*  
Boolean to prevent ddns from modifying the corresponding Route53 record   
The deletion/omission of an Item will also prevent Route53 record creation or modification.   
See [Security Considerations](#security-considerations)  

* *mac_address*  
Set the mac address of the host to associate with the Route53 record   
Optional, used by [Network Discovery](#network-discovery)

* *read_privilege*  
Boolean to allow read access by another host   
Optional, used by [Network Discovery](#network-discovery)  

* *shared_secret*  
Password used by client to modify Route53 record   
See [Security Considerations/Authentication](#authentication)  
Optional: [Network Discovery](#network-discovery) uses *shared_secret* to group records  
 
* *ttl*  
Set for (in seconds) custom Route53 record TTL.

###### *Navigate* | [*Top*](#route53-dynamic-dns-with-lambda) | [*Setup*](#setup-guide) | [*Outputs*](#cloudformation-stack-outputs) | [*Configuration*](#configuration-guide) | [*Security*](#security-considerations) | [*Network Discovery*](#network-discovery) | [*API Reference*](#api-reference) |   
--- 
### Security Considerations    

#### Route53/DNS 
* The ddns system gains permissions to modify records in the configured Route53 Zone.  
If you are concerned about allowing the system to modify an existing Zone, you can create a  
new Zone as a delegated subdomain.   
See [*Route53 Setup*](./documentation/route53_setup.md) for instructions.  
Note that delegated subdomains do not work with [private zones.](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/hosted-zone-private-considerations.html)    

* The ddns system will not modify or create a record if a matching Item is not found in DynamoDB  
or a matching matching Item is found, but it's *lock_record* attribute is *true*.  


#### Authentication and Authorization
* Reference for API Gateway [API Keys / Usage Plans](https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-api-usage-plans.html) 

* When the client makes an API request to modify a record, it passes a token generated by hashing:  
-The public IP of the requesting host or network  
-The hostname to be set  
-The shared secret associated with the hostname's Item in DynamoDB  
*Note that the public IP is discovered by an initial client request to the API in get mode.  
Then API then reflects the client's public IP in the JSON response.*  

* The API (via Lambda) re-creates and matches the hash the IP of the request and a lookup of the  
*shared_secret* attribute from DynamoDB.  

* It then sets the dns record to the requestor's public ipv4 or ipv6 address.  

* When setting a private IP, the client can request that any valid ipv4 or ipv6 address be set into the record.  
If the *allow_internal* configuration Attribute is set to *false*, the system will not set arbitrary IP addresses.  

#### Known issues  
* The system could be vulnerable to request-replay attack via a man-in-the-middle.  
As designed, it relies on the security of ssl/tls to secure transmissions.  
We are evaluating whether it makes sense to add a timestamp to the hash to mitigate this.  

* Publishing private ipv4 addresses to a public Route53 Zone leaks those addresses publicly.  

###### *Navigate* | [*Top*](#route53-dynamic-dns-with-lambda) | [*Setup*](#setup-guide) | [*Outputs*](#cloudformation-stack-outputs) | [*Configuration*](#configuration-guide) | [*Security*](#security-considerations) | [*Network Discovery*](#network-discovery) | [*API Reference*](#api-reference) |   
---
### Network Discovery       
Network Discovery enables a single host to set dns entries for other hosts on the same network.  
This removes the need to install a client on all hosts, and enables creation of dns entries for devices unable to run a client. 
* To enable this feature, create host groups in the DynamnoDB config table.  
* Hosts with matching *shared_secret* Attributes and the *read_privilege* set to *true* form a group.  
* The *mac_address* Attribute must also be set correctly in DynamoDB for each host in the group.  
* Any host within a group can make requests to set Route53 records on behalf of other hosts in the group.  

Process:  
* The client makes an authenticated *list_hosts* request to the API.  
* The API returns json containing the *hostname*, *mac_address* & *record_type* for each host in the group.  
` {"record_type": "A","hostname": "foo.example.com.","mac_address": "51:6B:00:A6:F5:77"}]`
* The client makes an ARP (ipv4) request to find the ip address of each host by mac address.    
`arp |grep 51:6B:00:A6:F5:77`   
`(192.168.0.20) at 51:6B:00:A6:F5:77 [ether]  on eth0`  
For ipv6, the client can use `ndp -an` or `ip -6 neigh` instead of ARP (depending on OS).  
* The client then makes the API request to set other host's dns using the discovered ip addresses.  
* A reference client *network-discovery.sh* is included.  It's a wrapper script that uses *route53-ddns-client.sh* to call the actual API.  
* The reference client uses local os cache via arp, ip or ndp commands to discover and match ip addresses to mac addresses.  
Note: The host running the network-discovery may not have all hosts in its cache at any given time.  
For ipv4, you could use nmap to scan the network.  This method is impractical for ipv6 considering the huge number of potential addresses.  
Network discovery will not work as implemented inside a VPC as VPC is unicast only.  
*If you have feedback on the utility of network-discovery or thoughts on improvements, please let us know!*

###### *Navigate* | [*Top*](#route53-dynamic-dns-with-lambda) | [*Setup*](#setup-guide) | [*Outputs*](#cloudformation-stack-outputs) | [*Configuration*](#configuration-guide) | [*Security*](#security-considerations) | [*Network Discovery*](#network-discovery) | [*API Reference*](#api-reference) |   
---
### API reference  

Examples of interacting with the API using curl  
* IP Address Reflector - *mode=get*  
`curl -q --ipv4 -s  https://ddns.example.com?mode=get`  
`curl -q --ipv6 -s  https://ddns.example.com?mode=get`  

* Using an API Key - required for all requests if enabled  
Replace `voN8GxIEvPf` with key published in your stack outputs.     
`curl -q --ipv4 -s -H 'x-api-key: voN8GxIEvPf' https://ddns.example.com?mode=get`  
`curl -q --ipv6 -s -H 'x-api-key: voN8GxIEvPf' "https://ddns.example.com?mode=set&hostname=foo.example.com&hash=ABCD123"`

* Generating the hash token needed for all other API requests  
`mySharedSecret=123abc`  
`myPublicIP=73.222.111.6`  
`myHostname=test.example.com.`  
*Note that hostname must end in a '.'*  
`echo -n "$myPublicIP$myHostname$mySharedSecret" | shasum -a 256`  

* Set public ip - *mode=set*  
`curl -q --ipv4 -s "https://ddns.example.com?mode=set&hostname=foo.example.com&hash=ABCD123"`  
`curl -q --ipv6 -s "https://ddns.example.com?mode=set&hostname=foo.example.com&hash=ABCD123"` 
 
* Set private ip - *mode=set*  
`curl -q -s "https://ddns.example.com?mode=set&hostname=foo.example.com&hash=ABCD123&internalIp=192.168.0.1"`  
`curl -q -s "https://ddns.example.com?mode=set&hostname=foo.example.com&hash=ABCD123&internalIp=2500:1ff3:e0e:4501:8cf0:c278:da3d:4120"`  
*Note that you can set either ipv4 or ipv6 private addresses regardless of the protocol used by curl.*   

* List hosts in group for [network discovery](#network-discovery) - *mode=list_hosts*  
`curl -q -s "https://ddns.example.com?mode=list_hosts&hostname=foo.example.com&hash=ABCD123"`  

###### *Navigate* | [*Top*](#route53-dynamic-dns-with-lambda) | [*Setup*](#setup-guide) | [*Outputs*](#cloudformation-stack-outputs) | [*Configuration*](#configuration-guide) | [*Security*](#security-considerations) | [*Network Discovery*](#network-discovery) | [*API Reference*](#api-reference) |   
--- 





