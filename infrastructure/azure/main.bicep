targetScope = 'subscription'

@allowed([
  'staging'
  'pilot'
])
param environmentName string

@description('Azure region for environment-scoped resources.')
param location string

@minLength(3)
@maxLength(12)
@description('Short lowercase product prefix used in resource names.')
param namePrefix string = 'yoranix'

@description('Required root domain for production pilot. Staging may use placeholder hostnames until custom domains are approved.')
param domainRoot string

@description('Dashboard application host name, for example app.example.com.')
param appHostName string

@description('Authenticated API host name, for example api.example.com.')
param apiHostName string

@description('Public widget API host name, for example widget-api.example.com.')
param widgetApiHostName string

@description('Widget iframe host name, for example widget.example.com.')
param widgetHostName string

@description('SDK/CDN host name, for example cdn.example.com.')
param cdnHostName string

@description('PostgreSQL administrator login name. The password is supplied securely at deployment time.')
param postgresAdministratorLogin string = 'yoranixadmin'

@secure()
@description('PostgreSQL administrator password. Do not provide this in checked-in parameter files.')
param postgresAdministratorPassword string

@description('PostgreSQL database name.')
param postgresDatabaseName string = 'chatbotweb'

@description('PostgreSQL Flexible Server SKU name.')
param postgresSkuName string = 'Standard_B1ms'

@description('PostgreSQL storage size in GiB.')
param postgresStorageGiB int = 64

@description('PostgreSQL backup retention in days.')
@minValue(7)
@maxValue(35)
param postgresBackupRetentionDays int = 7

@description('API Container App CPU allocation.')
param apiCpu string = '1.0'

@description('API Container App memory allocation.')
param apiMemory string = '2Gi'

@description('Web Container App CPU allocation.')
param webCpu string = '0.5'

@description('Web Container App memory allocation.')
param webMemory string = '1Gi'

@description('Minimum replicas for API and web apps.')
param minReplicas int = 1

@description('Maximum replicas for API and web apps.')
param maxReplicas int = 3

@description('Provision Azure Cache for Redis for distributed public rate limiting and queues.')
param enableRedis bool = true

@description('Provision a no-ingress worker Container App placeholder for future ingestion/embedding jobs.')
param enableWorker bool = false

@description('Container image tag or digest placeholder used by initial Container App definitions until CI/CD injects immutable image digests.')
param initialImageTag string = 'bootstrap-placeholder'

@description('GitHub repository slug used in resource tags and OIDC documentation.')
param githubRepository string = 'Kera24/ChatBotWeb'

@description('Release channel for this environment.')
@allowed([
  'staging'
  'pilot'
])
param releaseChannel string = environmentName

var resourceToken = toLower('${namePrefix}-${environmentName}')
var resourceGroupName = '${resourceToken}-rg'
var tags = {
  environment: environmentName
  service: 'chatbotweb'
  managed_by: 'bicep'
  repository: githubRepository
  release_channel: releaseChannel
  data_classification: environmentName == 'pilot' ? 'controlled-pilot' : 'synthetic-staging'
}

resource environmentResourceGroup 'Microsoft.Resources/resourceGroups@2023-07-01' = {
  name: resourceGroupName
  location: location
  tags: tags
}

module monitoring 'modules/monitoring.bicep' = {
  name: '${resourceToken}-monitoring'
  scope: environmentResourceGroup
  params: {
    location: location
    namePrefix: namePrefix
    environmentName: environmentName
    logRetentionDays: environmentName == 'pilot' ? 30 : 14
    tags: tags
  }
}

module registry 'modules/container-registry.bicep' = {
  name: '${resourceToken}-acr'
  scope: environmentResourceGroup
  params: {
    location: location
    namePrefix: namePrefix
    environmentName: environmentName
    tags: tags
  }
}

module keyVault 'modules/key-vault.bicep' = {
  name: '${resourceToken}-kv'
  scope: environmentResourceGroup
  params: {
    location: location
    namePrefix: namePrefix
    environmentName: environmentName
    tags: tags
  }
}

module storage 'modules/storage.bicep' = {
  name: '${resourceToken}-storage'
  scope: environmentResourceGroup
  params: {
    location: location
    namePrefix: namePrefix
    environmentName: environmentName
    tags: tags
  }
}

module postgres 'modules/postgres.bicep' = {
  name: '${resourceToken}-postgres'
  scope: environmentResourceGroup
  params: {
    location: location
    namePrefix: namePrefix
    environmentName: environmentName
    administratorLogin: postgresAdministratorLogin
    administratorPassword: postgresAdministratorPassword
    databaseName: postgresDatabaseName
    skuName: postgresSkuName
    storageGiB: postgresStorageGiB
    backupRetentionDays: postgresBackupRetentionDays
    tags: tags
  }
}

module redis 'modules/redis.bicep' = if (enableRedis) {
  name: '${resourceToken}-redis'
  scope: environmentResourceGroup
  params: {
    location: location
    namePrefix: namePrefix
    environmentName: environmentName
    tags: tags
  }
}

module apps 'modules/container-apps.bicep' = {
  name: '${resourceToken}-apps'
  scope: environmentResourceGroup
  params: {
    location: location
    namePrefix: namePrefix
    environmentName: environmentName
    logAnalyticsCustomerId: monitoring.outputs.logAnalyticsCustomerId
    logAnalyticsSharedKey: monitoring.outputs.logAnalyticsSharedKey
    acrLoginServer: registry.outputs.loginServer
    keyVaultName: keyVault.outputs.keyVaultName
    postgresHostName: postgres.outputs.postgresHostName
    databaseName: postgresDatabaseName
    appHostName: appHostName
    apiHostName: apiHostName
    widgetApiHostName: widgetApiHostName
    widgetHostName: widgetHostName
    cdnHostName: cdnHostName
    apiCpu: apiCpu
    apiMemory: apiMemory
    webCpu: webCpu
    webMemory: webMemory
    minReplicas: minReplicas
    maxReplicas: maxReplicas
    initialImageTag: initialImageTag
    enableWorker: enableWorker
    enableRedis: enableRedis
    redisHostName: enableRedis ? redis.outputs.redisHostName : ''
    tags: tags
  }
}

module frontDoor 'modules/front-door.bicep' = {
  name: '${resourceToken}-frontdoor'
  scope: environmentResourceGroup
  params: {
    location: 'global'
    namePrefix: namePrefix
    environmentName: environmentName
    appHostName: appHostName
    apiHostName: apiHostName
    widgetApiHostName: widgetApiHostName
    widgetHostName: widgetHostName
    cdnHostName: cdnHostName
    webContainerAppFqdn: apps.outputs.webFqdn
    apiContainerAppFqdn: apps.outputs.apiFqdn
    widgetStaticHostName: storage.outputs.widgetStaticHostName
    tags: tags
  }
}

output resourceGroupName string = environmentResourceGroup.name
output acrLoginServer string = registry.outputs.loginServer
output apiContainerAppName string = apps.outputs.apiContainerAppName
output webContainerAppName string = apps.outputs.webContainerAppName
output migrationJobName string = apps.outputs.migrationJobName
output keyVaultName string = keyVault.outputs.keyVaultName
output postgresHostName string = postgres.outputs.postgresHostName
output documentStorageAccountName string = storage.outputs.documentStorageAccountName
output widgetStaticStorageAccountName string = storage.outputs.widgetStaticStorageAccountName
output frontDoorProfileName string = frontDoor.outputs.frontDoorProfileName
output frontDoorEndpointHostName string = frontDoor.outputs.frontDoorEndpointHostName
output domainModel object = {
  app: appHostName
  api: apiHostName
  widgetApi: widgetApiHostName
  widget: widgetHostName
  cdn: cdnHostName
}
