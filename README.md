# route53-dynamic-dns-with-lambda
A Dynamic DNS system built with API Gateway, Lambda &amp; Route 53.  

The code in this repository is meant to supplement the blog post which fully describes the project.   
See: [Building a Serverless Dynamic DNS System with AWS](https://medium.com/aws-activate-startup-blog/building-a-serverless-dynamic-dns-system-with-aws-a32256f0a1d8) 

Read 'Setup_Instructions.md' for instructions on implementing the system.  

3/13/18:
Added support for setting the internal IP to DNS
Files modified for this feature: 
api_mapping_template, dynamic_dns_lambda_client.sh & dynamic_dns_client.sh