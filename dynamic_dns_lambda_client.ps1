#PowerShell: 
# to enable scripts to run, you need to change execution policy to allow 3rd party scripts to run.
# https://technet.microsoft.com/en-us/library/hh849812.aspx
# Set-ExecutionPolicy unrestricted
#

Param(
[Parameter(Mandatory=$True,Position=1)][string]$myHostname,
[Parameter(Mandatory=$True,Position=2)][string]$mySharedSecret,
[Parameter(Mandatory=$True,Position=3)][string]$myAPIURL)

$helptext = 'The script requires hostname and shared secret arguments
    ie: dynamic_dns_lambda_client.ps1 host1.dyn.example.com. sharedsecret "abc123.execute-api.us-west-2.amazonaws.com/prod"'
$helptext


$getURL = $myAPIURL + "?mode=get"
$webRequest = Invoke-WebRequest -URI $getURL

$myIP = $webRequest.Content.Replace('{"return_message": "', '').Replace('", "return_status": "success"}','')

$message = $myIP + $myHostname + $mySharedSecret

$sha256 = New-Object System.Text.StringBuilder 
[System.Security.Cryptography.HashAlgorithm]::Create("SHA256").ComputeHash([System.Text.Encoding]::UTF8.GetBytes($message))|%{ 
[Void]$sha256.Append($_.ToString("x2")) 
} 
$message = $sha256.ToString() 
$setURL = $myAPIURL + "?mode=set&hostname=" + $myHostname + "&hash=" + $message
$webRequest = Invoke-WebRequest -URI $setURL

$webRequest.Content