          import boto3
          import os
          import zipfile
          import http.client
          import uuid
          import urllib.parse
          import json
           
          print('Loading function')
          from botocore.client import Config
          s3 = boto3.client('s3')
          
          def send_response(request, response, status=None, reason=None):
              """ Send our response to the pre-signed URL supplied by CloudFormation"""
              if status is not None:
                  response['Status'] = status
              if reason is not None:
                  response['Reason'] = reason
              if 'ResponseURL' in request and request['ResponseURL']:
                  url = urllib.parse.urlparse(request['ResponseURL'])
                  body = json.dumps(response)
                  https = http.client.HTTPSConnection(url.hostname)
                  https.request('PUT', url.path+'?'+url.query, body)
              return response
          
          def lambda_handler(event, context):
              response = {
                  'StackId': event['StackId'],
                  'RequestId': event['RequestId'],
                  'LogicalResourceId': event['LogicalResourceId'],
                  'Status': 'SUCCESS'
              }
              # PhysicalResourceId is meaningless here, but CloudFormation requires it
              if 'PhysicalResourceId' in event:
                  response['PhysicalResourceId'] = event['PhysicalResourceId']
              else:
                  response['PhysicalResourceId'] = str(uuid.uuid4())
          
              # There is nothing to do for a delete request
              if event['RequestType'] == 'Delete':
                  return send_response(event, response)
              ## Get the S3 Bucket passed in from CFN
              s3TargetBucket=event['ResourceProperties']['s3TargetBucket']
              ## Get the file contents to put in S3 from CFN
              lambda_body=event['ResourceProperties']['lambda_body']
              file_name=event['ResourceProperties']['file_name']
              zip_file = '/tmp/' + file_name + '.zip'
              s3_key = file_name + '.zip'
              ## Write the body variable to a file
              ## and change perms to add exec
              try:
                os.remove('/tmp/index.py') # delete old file in case function is re-used
              except:
                pass
              lambda_file = open('/tmp/index.py', 'w')
              os.chmod('/tmp/index.py', 0o777)
              lambda_file.write(lambda_body)
              lambda_file.close()
              ## Build the zip archive
              zip_archive = zipfile.ZipFile(zip_file, 'w')
              zip_archive.write('/tmp/index.py', 'index.py')
              zip_archive.close()
              zip_file = open(zip_file, 'r')
          
              ## Put the archive in S3
              try:
                  s3_response = s3.put_object(
                  Body= zip_file.read(),
                  Bucket= s3TargetBucket,
                  Key= s3_key,
                  )
                  response['Data'] = {
                      's3Success': 'true',
                      file_name + '-S3ObjectVersion': s3_response['VersionId']
                  }
                  response['Reason'] = s3_key + ' added to S3'
                  print(str(s3_response['VersionId']))
              except Exception as E:
                response['Reason'] = 'Event Failed - See CloudWatch logs for the Lamba function backing the custom resource for details'
                ## Un-comment the line below to send a true failure to CFN
                ## will cause a stack rollback on failure and can leave the stack in a state that requires deletion.
                #response['Status'] = 'FAILED'
              # Log it!
              print(str(s3_response))
              print('Response Text: ' + str(response))
              return send_response(event, response)
          
          