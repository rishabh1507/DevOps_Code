import subprocess, json
import azUtils
import DeploymentTargetGraphClient
import requests
import BaseSettings
import AzureBeaconStartup

TENANT_ID = ''
SUBSCRIPTION_ID = ''

def _login():
    subprocess.call(['az', 'login', '--tenant', TENANT_ID])
    subprocess.call(['az', 'account', 'set', '-s', SUBSCRIPTION_ID])
    creds, _ = azUtils.get_azure_cli_credentials(subscription_id=SUBSCRIPTION_ID)
    access_token = creds.get_token('/.default').token
    return access_token

new_quota_limit = 12
location_id = 'westeurope'
provider_id = 'Microsoft.Compute'
resource_id = 'standardFSv2Family'
req_url = f'https://management.azure.com/subscriptions/{SUBSCRIPTION_ID}/providers/{provider_id}/locations/{location_id}/providers/Microsoft.Quota/quotas/{resource_id}'
params = {'api-version': '2023-02-01'}

access_token = _login()
result = requests.get(req_url, params=params, headers={'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'}).json()
print(f'GET Response= {json.dumps(result, indent=4)}')

data = {
  "properties": {
    "limit": {
      "limitObjectType": "LimitValue",
      "value": new_quota_limit
    },
    "name": {
      "value": resource_id
    }
  }
}

result = requests.patch(req_url, params=params, json=data, headers={'Authorization': f'Bearer {access_token}'}).json()
print(f'PATCH Response= {json.dumps(result, indent=4)}')