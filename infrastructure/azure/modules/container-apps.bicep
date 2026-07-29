param location string
param namePrefix string
param environmentName string
param logAnalyticsCustomerId string
@secure()
param logAnalyticsSharedKey string
param tags object

var envName = '${namePrefix}-${environmentName}-cae'
var apiName = '${namePrefix}-${environmentName}-ca-api'
var webName = '${namePrefix}-${environmentName}-ca-web'
var workerName = '${namePrefix}-${environmentName}-ca-worker'
var migrationJobName = '${namePrefix}-${environmentName}-job-migrate'
var apiIdentityName = '${namePrefix}-${environmentName}-id-api'
var webIdentityName = '${namePrefix}-${environmentName}-id-web'
var migrationIdentityName = '${namePrefix}-${environmentName}-id-migration'
var workerIdentityName = '${namePrefix}-${environmentName}-id-worker'

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

resource apiIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: apiIdentityName
  location: location
  tags: union(tags, { component: 'api' })
}

resource webIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: webIdentityName
  location: location
  tags: union(tags, { component: 'web' })
}

resource migrationIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: migrationIdentityName
  location: location
  tags: union(tags, { component: 'migration' })
}

resource workerIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: workerIdentityName
  location: location
  tags: union(tags, { component: 'worker' })
}

output managedEnvironmentName string = managedEnvironment.name
output managedEnvironmentId string = managedEnvironment.id
output apiContainerAppName string = apiName
output webContainerAppName string = webName
output workerContainerAppName string = workerName
output migrationJobName string = migrationJobName
output syntheticWidgetBootstrapJobName string = syntheticWidgetBootstrapJobName
output apiManagedIdentityId string = apiIdentity.id
output webManagedIdentityId string = webIdentity.id
output migrationManagedIdentityId string = migrationIdentity.id
output workerManagedIdentityId string = workerIdentity.id
output apiPrincipalId string = apiIdentity.properties.principalId
output webPrincipalId string = webIdentity.properties.principalId
output migrationPrincipalId string = migrationIdentity.properties.principalId
output workerPrincipalId string = workerIdentity.properties.principalId
