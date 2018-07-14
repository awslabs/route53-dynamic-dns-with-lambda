#PowerShell: 
# to enable scripts to run, you need to change execution policy to allow 3rd party scripts to run.
# https://technet.microsoft.com/en-us/library/hh849812.aspx
# To launch a subshell to run the script, use:
# powershell –ExecutionPolicy Bypass
#

Param(
[Parameter(Mandatory=$True,Position=1)][string]$myHostname,
[Parameter(Mandatory=$True,Position=2)][string]$mySharedSecret,
[Parameter(Mandatory=$True,Position=3)][string]$myAPIURL,
[Parameter(Mandatory=$True,Position=4)][string]$myAPIKEY)

#$myHostname = "must.end.in.dot."
#$mySharedSecret = "CHECKDYNAMODB"
#$myAPIURL = "https://" + "CHECKDYNAMODB"
#$myAPIKEY = "CHECKDYNAMODB"

$helptext = "If it doesn't work, call Microsoft ;)"
$helptext

$getURL = $myAPIURL + "?mode=get"
$webRequest = Invoke-WebRequest -Headers @{"x-api-key"="$myAPIKEY"} -URI $getURL

#$webRequest.Content
$myIP = $webRequest.Content.Replace('{"return_message": "', '').Replace('", "return_status": "success"}','')

$message = $myIP + $myHostname + $mySharedSecret
$sha256 = New-Object System.Text.StringBuilder 
[System.Security.Cryptography.HashAlgorithm]::Create("SHA256").ComputeHash([System.Text.Encoding]::UTF8.GetBytes($message))|%{ 
[Void]$sha256.Append($_.ToString("x2")) 
} 
$message = $sha256.ToString() 
$setURL = $myAPIURL + "?mode=set&hostname=" + $myHostname + "&hash=" + $message + "&internalIp=" + $myIp
$webRequest = Invoke-WebRequest -Headers @{"x-api-key"="$myAPIKEY"} -URI $setURL

$webRequest.Content