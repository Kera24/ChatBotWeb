param location string
param namePrefix string
param environmentName string
param logAnalyticsCustomerId string
@secure()
param logAnalyticsSharedKey string
param acrLoginServer string
param keyVaultName string
param postgresHostName string
param databaseName string
param appHostName string
param apiHostName string
param widgetApiHostName string
param widgetHostName string
param cdnHostName string
param apiCpu string
param apiMemory string
param webCpu string
param webMemory string
param minReplicas int
param maxReplicas int
param initialImageTag string
param enableWorker bool
param enableRedis bool
param redisHostName string
param tags object

var envName = '${namePrefix}-${environmentName}-cae'
var apiName = '${namePrefix}-${environmentName}-ca-api'
var webName = '${namePrefix}-${environmentName}-ca-web'
var workerName = '${namePrefix}-${environmentName}-ca-worker'
var migrationJobName = '${namePrefix}-${environmentName}-job-migrate'
var keyVaultUri = 'https://${keyVaultName}.vault.azure.net'
var apiImage = '${acrLoginServer}/chatbotweb-api:${initialImageTag}'
var webImage = '${acrLoginServer}/chatbotweb-web:${initialImageTag}'
var workerImage = apiImage

resource managedEnvironment 'Microsoft.App/managedEnvironments@2023-05-01' = {
  name: envName
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalyticsCustomerId
        sharedKey: logAnalyticsSharedKey
      }
    }
    zoneRedundant: false
  }
}

resource apiApp 'Microsoft.App/containerApps@2023-05-01' = {
  name: apiName
  location: location
  tags: union(tags, { component: 'api' })
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    managedEnvironmentId: managedEnvironment.id
    configuration: {
      activeRevisionsMode: 'Multiple'
      registries: [
        {
          server: acrLoginServer
          identity: 'system'
        }
      ]
      secrets: [
        {
          name: 'database-url'
          keyVaultUrl: '${keyVaultUri}/secrets/api-database-url'
          identity: 'system'
        }
        {
          name: 'redis-url'
          keyVaultUrl: '${keyVaultUri}/secrets/api-redis-url'
          identity: 'system'
        }
        {
          name: 'rate-limit-identity-secret'
          keyVaultUrl: '${keyVaultUri}/secrets/rate-limit-identity-secret'
          identity: 'system'
        }
        {
          name: 'public-session-token-hash-secret'
          keyVaultUrl: '${keyVaultUri}/secrets/public-session-token-hash-secret'
          identity: 'system'
        }
        {
          name: 'public-message-idempotency-hash-secret'
          keyVaultUrl: '${keyVaultUri}/secrets/public-message-idempotency-hash-secret'
          identity: 'system'
        }
        {
          name: 'preview-grant-signing-secret'
          keyVaultUrl: '${keyVaultUri}/secrets/preview-grant-signing-secret'
          identity: 'system'
        }
      ]
      ingress: {
        external: true
        targetPort: 8000
        transport: 'http'
        allowInsecure: false
        traffic: [
          {
            latestRevision: true
            weight: 100
          }
        ]
      }
    }
    template: {
      revisionSuffix: 'bootstrap'
      containers: [
        {
          name: 'api'
          image: apiImage
          env: [
            { name: 'APP_ENV', value: environmentName == 'pilot' ? 'production' : 'staging' }
            { name: 'PHASE', value: 'controlled-pilot' }
            { name: 'SERVICE_NAME', value: 'chatbotweb-api' }
            { name: 'VERSION', value: initialImageTag }
            { name: 'API_V1_PREFIX', value: '/api/v1' }
            { name: 'DATABASE_URL', secretRef: 'database-url' }
            { name: 'REDIS_URL', secretRef: 'redis-url' }
            { name: 'RATE_LIMIT_IDENTITY_SECRET', secretRef: 'rate-limit-identity-secret' }
            { name: 'PUBLIC_SESSION_TOKEN_HASH_SECRET', secretRef: 'public-session-token-hash-secret' }
            { name: 'PUBLIC_MESSAGE_IDEMPOTENCY_HASH_SECRET', secretRef: 'public-message-idempotency-hash-secret' }
            { name: 'PUBLIC_WIDGET_ASSET_BASE_URL', value: 'https://${cdnHostName}' }
            { name: 'PUBLIC_WIDGETS_ENABLED', value: 'true' }
            { name: 'PUBLIC_WIDGET_MESSAGES_ENABLED', value: 'true' }
            { name: 'PUBLIC_WIDGET_PILOT_ENFORCEMENT_ENABLED', value: environmentName == 'pilot' ? 'true' : 'false' }
            { name: 'RATE_LIMIT_LOCAL_FALLBACK_ENABLED', value: 'false' }
          ]
          resources: {
            cpu: json(apiCpu)
            memory: apiMemory
          }
          probes: [
            {
              type: 'Liveness'
              httpGet: {
                path: '/health/live'
                port: 8000
                scheme: 'HTTP'
              }
              initialDelaySeconds: 15
              periodSeconds: 30
              timeoutSeconds: 5
              failureThreshold: 3
            }
            {
              type: 'Readiness'
              httpGet: {
                path: '/health/ready'
                port: 8000
                scheme: 'HTTP'
              }
              initialDelaySeconds: 20
              periodSeconds: 30
              timeoutSeconds: 5
              failureThreshold: 3
            }
          ]
        }
      ]
      scale: {
        minReplicas: minReplicas
        maxReplicas: maxReplicas
      }
    }
  }
}

resource webApp 'Microsoft.App/containerApps@2023-05-01' = {
  name: webName
  location: location
  tags: union(tags, { component: 'web' })
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    managedEnvironmentId: managedEnvironment.id
    configuration: {
      activeRevisionsMode: 'Multiple'
      registries: [
        {
          server: acrLoginServer
          identity: 'system'
        }
      ]
      secrets: [
        {
          name: 'web-auth-secret'
          keyVaultUrl: '${keyVaultUri}/secrets/web-auth-secret'
          identity: 'system'
        }
      ]
      ingress: {
        external: true
        targetPort: 3000
        transport: 'http'
        allowInsecure: false
        traffic: [
          {
            latestRevision: true
            weight: 100
          }
        ]
      }
    }
    template: {
      revisionSuffix: 'bootstrap'
      containers: [
        {
          name: 'web'
          image: webImage
          env: [
            { name: 'NODE_ENV', value: 'production' }
            { name: 'NEXT_PUBLIC_API_BASE_URL', value: 'https://${apiHostName}' }
            { name: 'NEXT_TELEMETRY_DISABLED', value: '1' }
            { name: 'VERSION', value: initialImageTag }
          ]
          resources: {
            cpu: json(webCpu)
            memory: webMemory
          }
        }
      ]
      scale: {
        minReplicas: minReplicas
        maxReplicas: maxReplicas
      }
    }
  }
}

resource workerApp 'Microsoft.App/containerApps@2023-05-01' = if (enableWorker) {
  name: workerName
  location: location
  tags: union(tags, { component: 'worker' })
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    managedEnvironmentId: managedEnvironment.id
    configuration: {
      activeRevisionsMode: 'Single'
      registries: [
        {
          server: acrLoginServer
          identity: 'system'
        }
      ]
      secrets: [
        {
          name: 'database-url'
          keyVaultUrl: '${keyVaultUri}/secrets/api-database-url'
          identity: 'system'
        }
        {
          name: 'redis-url'
          keyVaultUrl: '${keyVaultUri}/secrets/api-redis-url'
          identity: 'system'
        }
      ]
      ingress: {
        external: false
      }
    }
    template: {
      containers: [
        {
          name: 'worker'
          image: workerImage
          command: [ 'python' ]
          args: [ '-m', 'app.worker' ]
          env: [
            { name: 'APP_ENV', value: environmentName == 'pilot' ? 'production' : 'staging' }
            { name: 'DATABASE_URL', secretRef: 'database-url' }
            { name: 'REDIS_URL', secretRef: 'redis-url' }
          ]
          resources: {
            cpu: 0.5
            memory: '1Gi'
          }
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 1
      }
    }
  }
}

resource migrationJob 'Microsoft.App/jobs@2023-05-01' = {
  name: migrationJobName
  location: location
  tags: union(tags, { component: 'migration' })
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    environmentId: managedEnvironment.id
    configuration: {
      triggerType: 'Manual'
      replicaTimeout: 1800
      replicaRetryLimit: 0
      manualTriggerConfig: {
        parallelism: 1
        replicaCompletionCount: 1
      }
      registries: [
        {
          server: acrLoginServer
          identity: 'system'
        }
      ]
      secrets: [
        {
          name: 'database-url'
          keyVaultUrl: '${keyVaultUri}/secrets/api-database-url'
          identity: 'system'
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'migration'
          image: apiImage
          command: [ 'python' ]
          args: [ '-m', 'alembic', 'upgrade', 'head' ]
          env: [
            { name: 'DATABASE_URL', secretRef: 'database-url' }
          ]
          resources: {
            cpu: 0.5
            memory: '1Gi'
          }
        }
      ]
    }
  }
}

output managedEnvironmentName string = managedEnvironment.name
output apiContainerAppName string = apiApp.name
output webContainerAppName string = webApp.name
output migrationJobName string = migrationJob.name
output apiFqdn string = apiApp.properties.configuration.ingress.fqdn
output webFqdn string = webApp.properties.configuration.ingress.fqdn
output apiPrincipalId string = apiApp.identity.principalId
output webPrincipalId string = webApp.identity.principalId
output workerPrincipalId string = enableWorker ? workerApp.identity.principalId : ''
output migrationPrincipalId string = migrationJob.identity.principalId
