import time
import boto3
route53 = boto3.client('route53')
dynamodb = boto3.client('dynamodb')
awslambda = boto3.client('lambda')
cloudformation = boto3.client('cloudformation')

newhz = False

# Check cloudformation stack has been deployed
try:
    stack = cloudformation.describe_stacks(StackName='DyndnsStack')
    if not (stack['Stacks'][0]['StackStatus'] == 'CREATE_COMPLETE' or stack['Stacks'][0]['StackStatus'] == 'UPDATE_COMPLETE'):
        print('Stack is being deployed try again in few minutes')
        exit()
except:
    print("Dyndns stack not found, ensure the right AWS CLI profile is being used.")
    exit()


# Get dynamodb table name and Lambda Function URL
resources = cloudformation.list_stack_resources(StackName='DyndnsStack')
for resource in resources['StackResourceSummaries']:
    if resource['ResourceType'] == 'AWS::DynamoDB::Table':
        table = resource['PhysicalResourceId']
    if resource['ResourceType'] == 'AWS::Lambda::Function':
        lambdafn = resource['PhysicalResourceId']
    else:
        pass

lambdaurl = awslambda.get_function_url_config(
    FunctionName=lambdafn)['FunctionUrl']

print('Hosted zone name, i.e. example.com.')
hzname = ""
while not hzname:
    hzname = input()
    if not hzname:
        print('####################################################')
        print('#                                                  #')
        print('# Hosted zone name is required and cannot be empty #')
        print('#                                                  #')
        print('####################################################\n')
        print('Hosted zone name, i.e. example.com.')
print('Hostname (www.'+hzname+')')
hostname = input() or "www."+hzname
print('Record set TTL (60)')
ttl = input() or 60

hz = route53.list_hosted_zones_by_name(
    MaxItems='1',
    DNSName=hzname
)
try:
    hzid = hz['HostedZones'][0]['Id'].split('/')[2]
    if hz['HostedZones'][0]['Name'] != hzname+'.':
        print(hz['HostedZones'][0]['Name'])
        raise Exception('Found hosted zone is not matching '+hzname)
except:
    print("Hosted zone " + hzname + " not found.")
    print("Do you want to create it? (y/n)")
    create=input()
    if create == 'y':
        try:
            route53.create_hosted_zone(
                Name= hzname,
                CallerReference= str(time.time())
            )
            hz=route53.list_hosted_zones_by_name(
                MaxItems= '1',
                DNSName= hzname
            )
            hzid=hz['HostedZones'][0]['Id'].split('/')[2]
            newhz=True
        except:
            print("Could not create hosted zone. Ensure '" +
                  hzname+"' is a valid domain name.")
            exit()
    else:
        print("You need an hosted zone to continue.")
        exit()

secret=""
while not secret:
    print('Enter the secret for the new record set.')
    secret=input()
    print('Confirm the secret: ')
    secret2=input()
    if secret != secret2:
        secret=""
        print('#####################################')
        print('#                                   #')
        print('# Secret does not match. Try again. #')
        print('#                                   #')
        print('#####################################')
        secret=""
        continue
print('##############################################')
print('#                                            #')
print('# The following configuration will be saved: #')
print('#                                            #')
print('  Host name:  '+hostname)
print('  Hosted zone id: '+hzid)
print('  Record set TTL: '+str(ttl))
print('  Secret: '+secret)
print('#                                            #')
print('#      do you want to continue? (y/n)        #')
print('#                                            #')
print('##############################################')
confirm=input()
if confirm == 'y':
    # Write configuration in dynamoddb
    print('\nSaving configuration...')
    try:
        dynamodb.put_item(
            TableName= table,
            Item = {
                'hostname': {
                    'S': hostname
                },
                'data': {
                    'S': '{"route_53_zone_id": "'+hzid+'","route_53_record_ttl": '+str(ttl)+',"shared_secret": "'+secret+'"}'
                }
            }
        )
        print('Configuration saved.\n')
        print('#####################################################')
        print('#                                                   #')
        print('# The Serverless Dynamic DNS solution is now ready. #')
        print('#                                                   #')
        print('#####################################################')
        print(
            '\n'+hostname+' can be updated with the following command:')
        print("./dyndns.sh -m set -u "+lambdaurl +
              " -h "+hostname+" -s "+secret)
        print('\n##########################################################################################\n')
    except:
        print("Could not save configuration.")
        exit()
else:
    print('Aborting.')
    if newhz:
        print('Do you want to delete the newly created hosted zone? (y/n)')
        delete = input()
        if delete == 'y':
            print('Deleting hosted zone...')
            route53.delete_hosted_zone(
                Id=hzid
            )
        else:
            print('Hosted zone '+hzname+'  not deleted.')
    exit()
