param location string
param namePrefix string
param environmentName string
param tags object

var compactPrefix = toLower(replace(namePrefix, '-', ''))
var documentStorageName = take('${compactPrefix}${environmentName}docs${uniqueString(resourceGroup().id)}', 24)
var widgetStorageName = take('${compactPrefix}${environmentName}widget${uniqueString(resourceGroup().id)}', 24)

resource documentStorage 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: documentStorageName
  location: location
  tags: union(tags, { data_classification: 'tenant-private-documents' })
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    accessTier: 'Hot'
    encryption: {
      keySource: 'Microsoft.Storage'
      services: {
        blob: {
          enabled: true
        }
        file: {
          enabled: true
        }
      }
    }
  }
}

resource documentBlobService 'Microsoft.Storage/storageAccounts/blobServices@2023-01-01' = {
  parent: documentStorage
  name: 'default'
  properties: {
    deleteRetentionPolicy: {
      enabled: true
      days: environmentName == 'pilot' ? 14 : 7
    }
    containerDeleteRetentionPolicy: {
      enabled: true
      days: environmentName == 'pilot' ? 14 : 7
    }
    cors: {
      corsRules: []
    }
  }
}

resource documentsContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  parent: documentBlobService
  name: 'documents'
  properties: {
    publicAccess: 'None'
  }
}

resource widgetStorage 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: widgetStorageName
  location: location
  tags: union(tags, { data_classification: 'public-widget-assets' })
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    accessTier: 'Hot'
    encryption: {
      keySource: 'Microsoft.Storage'
      services: {
        blob: {
          enabled: true
        }
      }
    }
  }
}

resource widgetBlobService 'Microsoft.Storage/storageAccounts/blobServices@2023-01-01' = {
  parent: widgetStorage
  name: 'default'
  properties: {
    staticWebsite: {
      enabled: true
      indexDocument: 'index.html'
      error404Document: 'index.html'
    }
    cors: {
      corsRules: [
        {
          allowedOrigins: [ '*' ]
          allowedMethods: [ 'GET', 'HEAD' ]
          maxAgeInSeconds: 3600
          exposedHeaders: [ 'ETag', 'Content-Length', 'Content-Type' ]
          allowedHeaders: [ '*' ]
        }
      ]
    }
  }
}

resource widgetContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  parent: widgetBlobService
  name: '$web'
  properties: {
    publicAccess: 'None'
  }
}

output documentStorageAccountName string = documentStorage.name
output widgetStaticStorageAccountName string = widgetStorage.name
output documentsContainerName string = documentsContainer.name
output widgetStaticHostName string = replace(replace(widgetStorage.properties.primaryEndpoints.web, 'https://', ''), '/', '')
output widgetStaticEndpoint string = widgetStorage.properties.primaryEndpoints.web
