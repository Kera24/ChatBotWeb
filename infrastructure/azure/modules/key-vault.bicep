param location string
param namePrefix string
param environmentName string
param tags object

var vaultName = toLower(replace('${namePrefix}-${environmentName}-kv', '-', ''))

resource vault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: vaultName
  location: location
  tags: tags
  properties: {
    tenantId: subscription().tenantId
    sku: {
      family: 'A'
      name: 'standard'
    }
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 90
    enablePurgeProtection: environmentName == 'pilot'
    publicNetworkAccess: 'Enabled'
  }
}

output keyVaultName string = vault.name
output keyVaultUri string = vault.properties.vaultUri
