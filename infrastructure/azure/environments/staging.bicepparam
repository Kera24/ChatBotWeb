using '../main.bicep'

param environmentName = 'staging'
param location = 'australiaeast'
param namePrefix = 'yoranix'
param domainRoot = 'staging.example.invalid'
param appHostName = 'app.staging.example.invalid'
param apiHostName = 'api.staging.example.invalid'
param widgetApiHostName = 'widget-api.staging.example.invalid'
param widgetHostName = 'widget.staging.example.invalid'
param cdnHostName = 'cdn.staging.example.invalid'
param postgresAdministratorLogin = 'yoranixadmin'
param postgresDatabaseName = 'chatbotweb'
param postgresSkuName = 'Standard_B1ms'
param postgresStorageGiB = 64
param postgresBackupRetentionDays = 7
param apiCpu = '1.0'
param apiMemory = '2Gi'
param webCpu = '0.5'
param webMemory = '1Gi'
param minReplicas = 1
param maxReplicas = 2
param enableRedis = true
param enableWorker = false
param initialImageTag = 'bootstrap-placeholder'
param githubRepository = 'Kera24/ChatBotWeb'
param releaseChannel = 'staging'
