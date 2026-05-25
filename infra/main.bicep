// Placeholder Bicep entry. Real modules wired in `infra-bicep` todo.
//
// Planned layout:
//   targetScope = 'resourceGroup'
//   - openai     : Cognitive Services account + gpt-realtime-2 deployment
//   - monitoring : Log Analytics + Application Insights
//   - containerApp: Managed Env + Container App (backend) + ACR + User MI + role assignment
//   - staticWebApp: SWA hosting the PWA
//
// Outputs:
//   - BACKEND_URL
//   - FRONTEND_URL
//   - AZURE_OPENAI_ENDPOINT
//   - APPLICATIONINSIGHTS_CONNECTION_STRING

targetScope = 'resourceGroup'

@minLength(1)
@description('Environment name used to derive resource names.')
param environmentName string

@description('Azure region for all resources.')
param location string = resourceGroup().location

@description('Tags applied to all resources.')
param tags object = {
  'azd-env-name': environmentName
  workload: 'gpt-realtime-2-vision-companion'
}

// TODO(infra-bicep): module openai 'modules/openai.bicep' = { ... }
// TODO(infra-bicep): module monitoring 'modules/monitoring.bicep' = { ... }
// TODO(infra-bicep): module containerApp 'modules/container-app.bicep' = { ... }
// TODO(infra-bicep): module staticWebApp 'modules/static-web-app.bicep' = { ... }

output AZURE_LOCATION string = location
output AZURE_ENV_NAME string = environmentName
