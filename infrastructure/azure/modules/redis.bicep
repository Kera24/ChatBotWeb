param location string
param namePrefix string
param environmentName string
param tags object

var cacheName = toLower(replace('${namePrefix}-${environmentName}-redis', '_', '-'))

resource redis 'Microsoft.Cache/redis@2023-08-01' = {
  name: cacheName
  location: location
  tags: tags
  properties: {
    sku: {
      name: 'Basic'
      family: 'C'
      capacity: 0
    }
    enableNonSslPort: false
    minimumTlsVersion: '1.2'
    publicNetworkAccess: 'Enabled'
    redisConfiguration: {
      'maxmemory-policy': 'allkeys-lru'
    }
  }
}

output redisName string = redis.name
output redisHostName string = redis.properties.hostName
