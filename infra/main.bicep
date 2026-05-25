// Vision Companion — full infrastructure entry.
targetScope = 'resourceGroup'

@minLength(1)
@description('Environment name used to derive resource names.')
param environmentName string

@description('Azure region for compute / monitoring / OpenAI.')
param location string = resourceGroup().location

@description('Region for Static Web App (limited regions).')
param swaLocation string = 'eastasia'

@description('Optional GitHub repo URL for SWA CI (e.g. https://github.com/turbo998/gpt-realtime-2-vision-companion).')
param repositoryUrl string = ''

@description('Realtime model name. Override to "gpt-4o-realtime-preview" if "gpt-realtime-2" is not yet in the region.')
param realtimeModelName string = 'gpt-realtime-2'

@description('Backend container image (push to ACR first, then pass <acr>.azurecr.io/vision-companion-backend:tag).')
param backendImage string = ''

@description('CORS allowed origins (comma separated).')
param allowedOrigins string = '*'

param tags object = {
  'azd-env-name': environmentName
  workload: 'gpt-realtime-2-vision-companion'
}

var prefix = toLower(replace(environmentName, '_', '-'))
var nameSuffix = uniqueString(resourceGroup().id, environmentName)

module openai 'modules/openai.bicep' = {
  name: 'openai'
  params: {
    name: '${prefix}-aoai-${nameSuffix}'
    location: location
    tags: tags
    realtimeModelName: realtimeModelName
    realtimeDeploymentName: 'gpt-realtime-2'
  }
}

module monitoring 'modules/monitoring.bicep' = {
  name: 'monitoring'
  params: {
    logAnalyticsName: '${prefix}-log-${nameSuffix}'
    applicationInsightsName: '${prefix}-appi-${nameSuffix}'
    location: location
    tags: tags
  }
}

module containerApp 'modules/container-app.bicep' = {
  name: 'containerApp'
  params: {
    envName: '${prefix}-cae-${nameSuffix}'
    containerAppName: '${prefix}-backend'
    acrName: toLower(replace('${prefix}acr${nameSuffix}', '-', ''))
    userIdentityName: '${prefix}-uami-${nameSuffix}'
    location: location
    tags: tags
    openAiAccountName: openai.outputs.accountName
    appInsightsConnectionString: monitoring.outputs.appInsightsConnectionString
    azureOpenAiEndpoint: openai.outputs.endpoint
    realtimeDeploymentName: openai.outputs.deploymentName
    allowedOrigins: allowedOrigins
    image: backendImage
    logAnalyticsId: monitoring.outputs.logAnalyticsId
  }
}

module staticWebApp 'modules/static-web-app.bicep' = {
  name: 'staticWebApp'
  params: {
    name: '${prefix}-web-${nameSuffix}'
    location: swaLocation
    tags: tags
    repositoryUrl: repositoryUrl
  }
}

output AZURE_LOCATION string = location
output AZURE_ENV_NAME string = environmentName
output AZURE_OPENAI_ENDPOINT string = openai.outputs.endpoint
output AZURE_OPENAI_REALTIME_DEPLOYMENT string = openai.outputs.deploymentName
output APPLICATIONINSIGHTS_CONNECTION_STRING string = monitoring.outputs.appInsightsConnectionString
output BACKEND_URL string = containerApp.outputs.backendUrl
output FRONTEND_URL string = staticWebApp.outputs.frontendUrl
output ACR_LOGIN_SERVER string = containerApp.outputs.acrLoginServer
output USER_IDENTITY_CLIENT_ID string = containerApp.outputs.userIdentityClientId
