param location string
param namePrefix string
param environmentName string
param managedEnvironmentName string
param acrLoginServer string
param keyVaultName string
param apiImage string
param webImage string
param apiIdentityId string
param webIdentityId string
param appHostName string
param apiHostName string
param widgetApiHostName string
param widgetHostName string
param cdnHostName string
param enableRedis bool
param apiCpu string = '1.0'
param apiMemory string = '2Gi'
param webCpu string = '0.5'
param webMemory string = '1Gi'
param minReplicas int = 1
param maxReplicas int = 3
param tags object

var apiName = '${namePrefix}-${environmentName}-ca-api'
var webName = '${namePrefix}-${environmentName}-ca-web'
var keyVaultUri = 'https://${keyVaultName}.vault.azure.net'
var releaseVersion = last(split(apiImage, ':'))
var redisSecrets = enableRedis ? [
  { name: 'redis-url', keyVaultUrl: '${keyVaultUri}/secrets/api-redis-url', identity: apiIdentityId }
] : []
var redisEnvironment = enableRedis ? [
  { name: 'REDIS_URL', secretRef: 'redis-url' }
] : []
var rateLimitLocalFallbackEnabled = enableRedis ? 'false' : (environmentName == 'staging' ? 'true' : 'false')

resource managedEnvironment 'Microsoft.App/managedEnvironments@2023-05-01' existing = {
  name: managedEnvironmentName
}

resource apiApp 'Microsoft.App/containerApps@2023-05-01' = {
  name: apiName
  location: location
  tags: union(tags, { component: 'api' })
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${apiIdentityId}': {}
    }
  }
  properties: {
    managedEnvironmentId: managedEnvironment.id
    configuration: {
      activeRevisionsMode: 'Multiple'
      registries: [
        {
          server: acrLoginServer
          identity: apiIdentityId
        }
      ]
      secrets: concat([
        { name: 'database-url', keyVaultUrl: '${keyVaultUri}/secrets/api-database-url', identity: apiIdentityId }
        { name: 'rate-limit-identity-secret', keyVaultUrl: '${keyVaultUri}/secrets/rate-limit-identity-secret', identity: apiIdentityId }
        { name: 'public-session-token-hash-secret', keyVaultUrl: '${keyVaultUri}/secrets/public-session-token-hash-secret', identity: apiIdentityId }
        { name: 'public-message-idempotency-hash-secret', keyVaultUrl: '${keyVaultUri}/secrets/public-message-idempotency-hash-secret', identity: apiIdentityId }
        { name: 'preview-grant-signing-secret', keyVaultUrl: '${keyVaultUri}/secrets/preview-grant-signing-secret', identity: apiIdentityId }
        { name: 'applicationinsights-connection-string', keyVaultUrl: '${keyVaultUri}/secrets/applicationinsights-connection-string', identity: apiIdentityId }
      ], redisSecrets)
      ingress: {
        external: true
        targetPort: 8000
        transport: 'http'
        allowInsecure: false
        traffic: [ { latestRevision: true, weight: 100 } ]
      }
    }
    template: {
      containers: [
        {
          name: 'api'
          image: apiImage
          env: concat([
            { name: 'APP_ENV', value: environmentName == 'pilot' ? 'production' : 'staging' }
            { name: 'PHASE', value: 'controlled-pilot' }
            { name: 'SERVICE_NAME', value: 'chatbotweb-api' }
            { name: 'VERSION', value: releaseVersion }
            { name: 'API_V1_PREFIX', value: '/api/v1' }
            { name: 'DATABASE_URL', secretRef: 'database-url' }
            { name: 'RATE_LIMIT_IDENTITY_SECRET', secretRef: 'rate-limit-identity-secret' }
            { name: 'PUBLIC_SESSION_TOKEN_HASH_SECRET', secretRef: 'public-session-token-hash-secret' }
            { name: 'PUBLIC_MESSAGE_IDEMPOTENCY_HASH_SECRET', secretRef: 'public-message-idempotency-hash-secret' }
            { name: 'PUBLIC_WIDGET_ASSET_BASE_URL', value: 'https://${cdnHostName}' }
            { name: 'PUBLIC_WIDGETS_ENABLED', value: 'true' }
            { name: 'PUBLIC_WIDGET_MESSAGES_ENABLED', value: 'true' }
            { name: 'PUBLIC_WIDGET_PILOT_ENFORCEMENT_ENABLED', value: environmentName == 'pilot' ? 'true' : 'false' }
            { name: 'RATE_LIMIT_LOCAL_FALLBACK_ENABLED', value: rateLimitLocalFallbackEnabled }
            { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', secretRef: 'applicationinsights-connection-string' }
            { name: 'AZURE_MONITOR_OPEN_TELEMETRY_ENABLED', value: 'true' }
            { name: 'AZURE_MONITOR_REQUIRE_CONNECTION_STRING', value: 'true' }
            { name: 'AZURE_MONITOR_SAMPLING_RATIO', value: '1.0' }
          ], redisEnvironment)
          resources: { cpu: json(apiCpu), memory: apiMemory }
          probes: [
            { type: 'Liveness', httpGet: { path: '/health/live', port: 8000, scheme: 'HTTP' }, initialDelaySeconds: 15, periodSeconds: 30, timeoutSeconds: 5, failureThreshold: 3 }
            { type: 'Readiness', httpGet: { path: '/health/ready', port: 8000, scheme: 'HTTP' }, initialDelaySeconds: 20, periodSeconds: 30, timeoutSeconds: 5, failureThreshold: 3 }
          ]
        }
      ]
      scale: { minReplicas: minReplicas, maxReplicas: maxReplicas }
    }
  }
}

resource webApp 'Microsoft.App/containerApps@2023-05-01' = {
  name: webName
  location: location
  tags: union(tags, { component: 'web' })
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${webIdentityId}': {}
    }
  }
  properties: {
    managedEnvironmentId: managedEnvironment.id
    configuration: {
      activeRevisionsMode: 'Multiple'
      registries: [ { server: acrLoginServer, identity: webIdentityId } ]
      secrets: [
        { name: 'web-auth-secret', keyVaultUrl: '${keyVaultUri}/secrets/web-auth-secret', identity: webIdentityId }
        { name: 'web-applicationinsights-connection-string', keyVaultUrl: '${keyVaultUri}/secrets/applicationinsights-connection-string', identity: webIdentityId }
      ]
      ingress: {
        external: true
        targetPort: 3000
        transport: 'http'
        allowInsecure: false
        traffic: [ { latestRevision: true, weight: 100 } ]
      }
    }
    template: {
      containers: [
        {
          name: 'web'
          image: webImage
          env: [
            { name: 'NODE_ENV', value: 'production' }
            { name: 'NEXT_PUBLIC_API_BASE_URL', value: 'https://${apiHostName}' }
            { name: 'NEXT_TELEMETRY_DISABLED', value: '1' }
            { name: 'VERSION', value: releaseVersion }
            { name: 'APP_ENV', value: environmentName == 'pilot' ? 'production' : 'staging' }
            { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', secretRef: 'web-applicationinsights-connection-string' }
          ]
          resources: { cpu: json(webCpu), memory: webMemory }
        }
      ]
      scale: { minReplicas: minReplicas, maxReplicas: maxReplicas }
    }
  }
}

output apiContainerAppName string = apiApp.name
output webContainerAppName string = webApp.name
output apiFqdn string = apiApp.properties.configuration.ingress.fqdn
output webFqdn string = webApp.properties.configuration.ingress.fqdn
