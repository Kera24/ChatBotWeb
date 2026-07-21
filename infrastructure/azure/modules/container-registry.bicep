param location string
param namePrefix string
param environmentName string
param tags object

var registryName = toLower(replace('${namePrefix}${environmentName}acr', '-', ''))

resource registry 'Microsoft.ContainerRegistry/registries@2023-01-01-preview' = {
  name: registryName
  location: location
  sku: {
    name: 'Standard'
  }
  tags: tags
  properties: {
    adminUserEnabled: false
    anonymousPullEnabled: false
    publicNetworkAccess: 'Enabled'
    policies: {
      quarantinePolicy: {
        status: 'disabled'
      }
      retentionPolicy: {
        days: 30
        status: 'enabled'
      }
      trustPolicy: {
        type: 'Notary'
        status: 'disabled'
      }
    }
  }
}

output registryName string = registry.name
output loginServer string = registry.properties.loginServer
