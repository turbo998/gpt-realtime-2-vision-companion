// Azure Static Web Apps hosting the PWA frontend.
@minLength(1)
param name string
param location string = 'eastasia'
param tags object = {}

@description('Optional GitHub repo URL to wire CI. Leave empty for manual deploys (azd / SWA CLI).')
param repositoryUrl string = ''
@description('GitHub branch.')
param branch string = 'main'

resource swa 'Microsoft.Web/staticSites@2023-12-01' = {
  name: name
  location: location
  tags: tags
  sku: {
    name: 'Free'
    tier: 'Free'
  }
  properties: {
    repositoryUrl: empty(repositoryUrl) ? null : repositoryUrl
    branch: empty(repositoryUrl) ? null : branch
    buildProperties: {
      appLocation: 'frontend'
      apiLocation: ''
      outputLocation: ''
    }
  }
}

output frontendUrl string = 'https://${swa.properties.defaultHostname}'
output staticSiteName string = swa.name
