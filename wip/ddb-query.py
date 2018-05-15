from __future__ import print_function # Python 2/3 compatibility
import boto3
import json
import decimal
from boto3.dynamodb.conditions import Key, Attr

boto3.setup_default_session(profile_name='sgreat-home')
#session = boto3.Session(profile_name='dev')

# Helper class to convert a DynamoDB item to JSON.
class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, decimal.Decimal):
            if o % 1 > 0:
                return float(o)
            else:
                return int(o)
        return super(DecimalEncoder, self).default(o)

#dynamodb = boto3.resource('dynamodb', region_name='us-west-2', endpoint_url="http://localhost:8000")
dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
client = boto3.client('dynamodb')
table = dynamodb.Table('dyn-gsi-test-config')
#index = dynamodb.Table('dyn-ddb-cleanup-test-config')

#print("Movies from 1985")

response = table.query(
    IndexName='shared_secret-index',
    KeyConditionExpression=Key('shared_secret').eq('9557F963635A77DD'),
    FilterExpression=Key('read_privilege').eq(True)
)
#    Select='ALL_ATTRIBUTES',
print(response)
for ddb_record in response['Items']:
    print(ddb_record['hostname'], ":", ddb_record['record_type'], ":", ddb_record['shared_secret'], ":", ddb_record['mac_address'])

#     UpdateExpression='SET last_checked = :now_time , last_accessed = :last_accessed',
#     ConditionExpression='attribute_exists(hostname) AND attribute_exists(record_type)',
#     ExpressionAttributeValues={
#         ':now_time': str(datetime.datetime.now()),
#         ':last_accessed': source_ip
#         }