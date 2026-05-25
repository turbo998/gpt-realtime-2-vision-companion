// Container Apps Environment + backend Container App + ACR + User-assigned MI
// with Cognitive Services OpenAI User role on the OpenAI account.
@minLength(1)
param envName string
@minLength(1)
param containerAppName string
@minLength(1)
param acrName string
@minLength(1)
param userIdentityName string
param location string = resourceGroup().location
param tags object = {}

@description('OpenAI account name (for role assignment).')
param openAiAccountName string

@description('App Insights connection string injected as env var.')
param appInsightsConnectionString string

@description('Azure OpenAI endpoint to expose as env var.')
param azureOpenAiEndpoint string

@description('Realtime deployment name for env var.')
param realtimeDeploymentName string = 'gpt-realtime-2'

@description('Allowed CORS origins, comma separated.')
param allowedOrigins string = '*'

@description('Container image (e.g. <acr>.azurecr.io/vision-companion-backend:tag). Empty deploys placeholder.')
param image string = ''

@description('Log Analytics workspace id for the managed env.')
param logAnalyticsId string

resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' existing = {
  name: last(split(logAnalyticsId, '/'))
}

resource acr 'Microsoft.ContainerRegistry/registries@2023-11-01-preview' = {
  name: acrName
  location: location
  tags: tags
  sku: { name: 'Basic' }
  properties: {
    adminUserEnabled: false
    publicNetworkAccess: 'Enabled'
  }
}

resource uami 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: userIdentityName
  location: location
  tags: tags
}

resource openAi 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = {
  name: openAiAccountName
}

// Cognitive Services OpenAI User
var openAiUserRoleId = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
resource raOpenAi 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(openAi.id, uami.id, openAiUserRoleId)
  scope: openAi
  properties: {
    principalId: uami.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', openAiUserRoleId)
  }
}

// AcrPull on the registry
var acrPullRoleId = '7f951dda-4ed3-4680-a7ca-43fe172d538d'
resource raAcr 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acr.id, uami.id, acrPullRoleId)
  scope: acr
  properties: {
    principalId: uami.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPullRoleId)
  }
}

resource env 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: envName
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logs.properties.customerId
        sharedKey: logs.listKeys().primarySharedKey
      }
    }
  }
}

var effectiveImage = empty(image) ? 'mcr.microsoft.com/k8se/quickstart:latest' : image

resource app 'Microsoft.App/containerApps@2024-03-01' = {
  name: containerAppName
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${uami.id}': {}
    }
  }
  dependsOn: [ raAcr, raOpenAi ]
  properties: {
    environmentId: env.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'
        corsPolicy: {
          allowedOrigins: split(allowedOrigins, ',')
          allowedMethods: [ '*' ]
          allowedHeaders: [ '*' ]
          allowCredentials: true
        }
      }
      registries: empty(image) ? [] : [
        {
          server: '${acrName}.azurecr.io'
          identity: uami.id
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'backend'
          image: effectiveImage
          resources: {
            cpu: json('0.5')
            memory: '1.0Gi'
          }
          env: [
            { name: 'AZURE_OPENAI_ENDPOINT', value: azureOpenAiEndpoint }
            { name: 'AZURE_OPENAI_REALTIME_DEPLOYMENT', value: realtimeDeploymentName }
            { name: 'AZURE_CLIENT_ID', value: uami.properties.clientId }
            { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsightsConnectionString }
            { name: 'ALLOWED_ORIGINS', value: allowedOrigins }
            { name: 'APP_ENV', value: 'azure' }
          ]
        }
      ]
      scale: { minReplicas: 1, maxReplicas: 3 }
    }
  }
}

output backendFqdn string = app.properties.configuration.ingress.fqdn
output backendUrl string = 'https://${app.properties.configuration.ingress.fqdn}'
output acrLoginServer string = acr.properties.loginServer
output userIdentityId string = uami.id
output userIdentityClientId string = uami.properties.clientId
