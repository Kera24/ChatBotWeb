param location string
param namePrefix string
param environmentName string
param managedEnvironmentName string
param acrLoginServer string
param keyVaultName string
param syntheticWidgetBootstrapImage string
param syntheticWidgetBootstrapIdentityId string
param cdnHostName string
param tags object

var syntheticWidgetBootstrapJobName = '${namePrefix}-${environmentName}-synth-widget-job'
var keyVaultUri = 'https://${keyVaultName}.vault.azure.net'
var releaseVersion = last(split(syntheticWidgetBootstrapImage, ':'))

resource managedEnvironment 'Microsoft.App/managedEnvironments@2023-05-01' existing = {
  name: managedEnvironmentName
}

resource syntheticWidgetBootstrapJob 'Microsoft.App/jobs@2023-05-01' = {
  name: syntheticWidgetBootstrapJobName
  location: location
  tags: union(tags, { component: 'synthetic-widget-bootstrap' })
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${syntheticWidgetBootstrapIdentityId}': {}
    }
  }
  properties: {
    environmentId: managedEnvironment.id
    configuration: {
      triggerType: 'Manual'
      replicaTimeout: 900
      replicaRetryLimit: 1
      manualTriggerConfig: {
        parallelism: 1
        replicaCompletionCount: 1
      }
      registries: [
        {
          server: acrLoginServer
          identity: syntheticWidgetBootstrapIdentityId
        }
      ]
      secrets: [
        {
          name: 'database-url'
          keyVaultUrl: '${keyVaultUri}/secrets/api-database-url'
          identity: syntheticWidgetBootstrapIdentityId
        }
        {
          name: 'public-session-token-hash-secret'
          keyVaultUrl: '${keyVaultUri}/secrets/public-session-token-hash-secret'
          identity: syntheticWidgetBootstrapIdentityId
        }
        {
          name: 'applicationinsights-connection-string'
          keyVaultUrl: '${keyVaultUri}/secrets/applicationinsights-connection-string'
          identity: syntheticWidgetBootstrapIdentityId
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'synthetic-widget-bootstrap'
          image: syntheticWidgetBootstrapImage
          command: [ 'python' ]
          args: [ '-m', 'app.operations.staging_synthetic_widgets' ]
          env: [
            { name: 'APP_ENV', value: 'staging' }
            { name: 'WIDGET_STAGING_SYNTHETIC_BOOTSTRAP', value: '1' }
            { name: 'PHASE', value: 'controlled-pilot' }
            { name: 'SERVICE_NAME', value: 'chatbotweb-api' }
            { name: 'VERSION', value: releaseVersion }
            { name: 'API_V1_PREFIX', value: '/api/v1' }
            { name: 'DATABASE_URL', secretRef: 'database-url' }
            { name: 'PUBLIC_SESSION_TOKEN_HASH_SECRET', secretRef: 'public-session-token-hash-secret' }
            { name: 'PUBLIC_WIDGET_ASSET_BASE_URL', value: 'https://${cdnHostName}' }
            { name: 'PUBLIC_WIDGETS_ENABLED', value: 'true' }
            { name: 'PUBLIC_WIDGET_MESSAGES_ENABLED', value: 'true' }
            { name: 'PUBLIC_WIDGET_PILOT_ENFORCEMENT_ENABLED', value: 'false' }
            { name: 'RATE_LIMIT_LOCAL_FALLBACK_ENABLED', value: 'true' }
            { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', secretRef: 'applicationinsights-connection-string' }
            { name: 'AZURE_MONITOR_OPEN_TELEMETRY_ENABLED', value: 'true' }
            { name: 'AZURE_MONITOR_REQUIRE_CONNECTION_STRING', value: 'false' }
            { name: 'AZURE_MONITOR_SAMPLING_RATIO', value: '1.0' }
          ]
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
        }
      ]
    }
  }
}

output syntheticWidgetBootstrapJobName string = syntheticWidgetBootstrapJob.name
