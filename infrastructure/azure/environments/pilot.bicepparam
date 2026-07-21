using '../main.bicep'

param environmentName = 'pilot'
param location = 'australiaeast'
param namePrefix = 'yoranix'
param domainRoot = '<approved-domain-required>'
param appHostName = 'app.<approved-domain-required>'
param apiHostName = 'api.<approved-domain-required>'
param widgetApiHostName = 'widget-api.<approved-domain-required>'
param widgetHostName = 'widget.<approved-domain-required>'
param cdnHostName = 'cdn.<approved-domain-required>'
param postgresAdministratorLogin = 'yoranixadmin'
param postgresDatabaseName = 'chatbotweb'
param postgresSkuName = 'Standard_B1ms'
param postgresStorageGiB = 128
param postgresBackupRetentionDays = 14
param apiCpu = '1.0'
param apiMemory = '2Gi'
param webCpu = '0.5'
param webMemory = '1Gi'
param minReplicas = 1
param maxReplicas = 3
param enableRedis = true
param enableWorker = false
param initialImageTag = 'bootstrap-placeholder'
param githubRepository = 'Kera24/ChatBotWeb'
param releaseChannel = 'pilot'
