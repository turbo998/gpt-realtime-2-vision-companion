// Azure OpenAI account + gpt-realtime-2 deployment.
@minLength(1)
param name string
param location string = resourceGroup().location
param tags object = {}

@description('Realtime model name (gpt-realtime-2 when available; gpt-4o-realtime-preview as fallback).')
param realtimeModelName string = 'gpt-realtime-2'

@description('Realtime model version. Leave empty to let Azure pick the default.')
param realtimeModelVersion string = ''

@description('Realtime deployment name surfaced to apps.')
param realtimeDeploymentName string = 'gpt-realtime-2'

@description('Capacity (TPM units) for the realtime deployment.')
param realtimeCapacity int = 1

resource account 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: name
  location: location
  tags: tags
  kind: 'OpenAI'
  sku: {
    name: 'S0'
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    customSubDomainName: name
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: false
  }
}

resource realtime 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: account
  name: realtimeDeploymentName
  sku: {
    name: 'GlobalStandard'
    capacity: realtimeCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: realtimeModelName
      version: empty(realtimeModelVersion) ? null : realtimeModelVersion
    }
    raiPolicyName: 'Microsoft.DefaultV2'
  }
}

output endpoint string = account.properties.endpoint
output accountId string = account.id
output accountName string = account.name
output deploymentName string = realtime.name
