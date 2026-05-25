// Log Analytics + Application Insights (workspace-based).
@minLength(1)
param logAnalyticsName string
@minLength(1)
param applicationInsightsName string
param location string = resourceGroup().location
param tags object = {}

resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: logAnalyticsName
  location: location
  tags: tags
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
    features: { searchVersion: 1 }
  }
}

resource appi 'Microsoft.Insights/components@2020-02-02' = {
  name: applicationInsightsName
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logs.id
    IngestionMode: 'LogAnalytics'
  }
}

output logAnalyticsId string = logs.id
output appInsightsConnectionString string = appi.properties.ConnectionString
output appInsightsInstrumentationKey string = appi.properties.InstrumentationKey
