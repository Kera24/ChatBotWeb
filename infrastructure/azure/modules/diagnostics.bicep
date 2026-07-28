param logAnalyticsWorkspaceId string
param containerAppsEnvironmentName string
param enableApplicationDiagnostics bool = true
param apiContainerAppName string
param webContainerAppName string
param frontDoorProfileName string
param postgresServerName string
param keyVaultName string
param documentStorageAccountName string
param widgetStorageAccountName string

resource containerAppsEnvironment 'Microsoft.App/managedEnvironments@2023-05-01' existing = {
  name: containerAppsEnvironmentName
}

resource apiContainerApp 'Microsoft.App/containerApps@2023-05-01' existing = if (enableApplicationDiagnostics) {
  name: apiContainerAppName
}

resource webContainerApp 'Microsoft.App/containerApps@2023-05-01' existing = if (enableApplicationDiagnostics) {
  name: webContainerAppName
}

resource frontDoorProfile 'Microsoft.Cdn/profiles@2023-05-01' existing = {
  name: frontDoorProfileName
}

resource postgresServer 'Microsoft.DBforPostgreSQL/flexibleServers@2023-06-01-preview' existing = {
  name: postgresServerName
}

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: keyVaultName
}

resource documentStorage 'Microsoft.Storage/storageAccounts@2023-01-01' existing = {
  name: documentStorageAccountName
}

resource widgetStorage 'Microsoft.Storage/storageAccounts@2023-01-01' existing = {
  name: widgetStorageAccountName
}

resource containerAppsEnvironmentDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: 'send-container-apps-to-log-analytics'
  scope: containerAppsEnvironment
  properties: {
    workspaceId: logAnalyticsWorkspaceId
    logs: [
      { category: 'ContainerAppConsoleLogs', enabled: true }
      { category: 'ContainerAppSystemLogs', enabled: true }
    ]
    metrics: [ { category: 'AllMetrics', enabled: true } ]
  }
}

resource apiDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = if (enableApplicationDiagnostics) {
  name: 'send-api-containerapp-to-log-analytics'
  scope: apiContainerApp
  properties: {
    workspaceId: logAnalyticsWorkspaceId
    metrics: [ { category: 'AllMetrics', enabled: true } ]
  }
}

resource webDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = if (enableApplicationDiagnostics) {
  name: 'send-web-containerapp-to-log-analytics'
  scope: webContainerApp
  properties: {
    workspaceId: logAnalyticsWorkspaceId
    metrics: [ { category: 'AllMetrics', enabled: true } ]
  }
}

resource frontDoorDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: 'send-frontdoor-to-log-analytics'
  scope: frontDoorProfile
  properties: {
    workspaceId: logAnalyticsWorkspaceId
    logs: [
      { category: 'FrontDoorAccessLog', enabled: true }
      { category: 'FrontDoorHealthProbeLog', enabled: true }
      { category: 'FrontDoorWebApplicationFirewallLog', enabled: true }
    ]
    metrics: [ { category: 'AllMetrics', enabled: true } ]
  }
}

resource postgresDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: 'send-postgres-to-log-analytics'
  scope: postgresServer
  properties: {
    workspaceId: logAnalyticsWorkspaceId
    logs: [ { category: 'PostgreSQLLogs', enabled: true } ]
    metrics: [ { category: 'AllMetrics', enabled: true } ]
  }
}

resource keyVaultDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: 'send-keyvault-to-log-analytics'
  scope: keyVault
  properties: {
    workspaceId: logAnalyticsWorkspaceId
    logs: [
      { category: 'AuditEvent', enabled: true }
      { category: 'AzurePolicyEvaluationDetails', enabled: true }
    ]
    metrics: [ { category: 'AllMetrics', enabled: true } ]
  }
}

resource documentStorageDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: 'send-document-storage-to-log-analytics'
  scope: documentStorage
  properties: {
    workspaceId: logAnalyticsWorkspaceId
    metrics: [ { category: 'Transaction', enabled: true } ]
  }
}

resource widgetStorageDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: 'send-widget-storage-to-log-analytics'
  scope: widgetStorage
  properties: {
    workspaceId: logAnalyticsWorkspaceId
    metrics: [ { category: 'Transaction', enabled: true } ]
  }
}
