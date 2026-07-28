param location string
param namePrefix string
param environmentName string
param managedEnvironmentName string
param acrLoginServer string
param keyVaultName string
param migrationImage string
param migrationIdentityId string
param tags object

var migrationJobName = '${namePrefix}-${environmentName}-job-migrate'
var keyVaultUri = 'https://${keyVaultName}.vault.azure.net'

resource managedEnvironment 'Microsoft.App/managedEnvironments@2023-05-01' existing = {
  name: managedEnvironmentName
}

resource migrationJob 'Microsoft.App/jobs@2023-05-01' = {
  name: migrationJobName
  location: location
  tags: union(tags, { component: 'migration' })
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${migrationIdentityId}': {}
    }
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
          identity: migrationIdentityId
        }
      ]
      secrets: [
        {
          name: 'database-url'
          keyVaultUrl: '${keyVaultUri}/secrets/api-database-url'
          identity: migrationIdentityId
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'migration'
          image: migrationImage
          command: [ 'python' ]
          args: [ '-m', 'alembic', 'upgrade', 'head' ]
          env: [
            { name: 'DATABASE_URL', secretRef: 'database-url' }
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

output migrationJobName string = migrationJob.name
