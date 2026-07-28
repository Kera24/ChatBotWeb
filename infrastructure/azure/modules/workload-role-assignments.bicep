param resourceGroupName string
param acrId string
param keyVaultId string
param storageAccountId string
param apiPrincipalId string
param webPrincipalId string
param migrationPrincipalId string
param workerPrincipalId string

var acrPullRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
var keyVaultSecretsUserRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')
var storageBlobDataContributorRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')

resource apiAcrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroupName, acrId, apiPrincipalId, 'AcrPull')
  properties: {
    roleDefinitionId: acrPullRoleDefinitionId
    principalId: apiPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource apiKeyVaultSecretsUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroupName, keyVaultId, apiPrincipalId, 'KeyVaultSecretsUser')
  properties: {
    roleDefinitionId: keyVaultSecretsUserRoleDefinitionId
    principalId: apiPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource apiStorageBlobDataContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroupName, storageAccountId, apiPrincipalId, 'StorageBlobDataContributor')
  properties: {
    roleDefinitionId: storageBlobDataContributorRoleDefinitionId
    principalId: apiPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource webAcrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroupName, acrId, webPrincipalId, 'AcrPull')
  properties: {
    roleDefinitionId: acrPullRoleDefinitionId
    principalId: webPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource webKeyVaultSecretsUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroupName, keyVaultId, webPrincipalId, 'KeyVaultSecretsUser')
  properties: {
    roleDefinitionId: keyVaultSecretsUserRoleDefinitionId
    principalId: webPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource migrationAcrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroupName, acrId, migrationPrincipalId, 'AcrPull')
  properties: {
    roleDefinitionId: acrPullRoleDefinitionId
    principalId: migrationPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource migrationKeyVaultSecretsUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroupName, keyVaultId, migrationPrincipalId, 'KeyVaultSecretsUser')
  properties: {
    roleDefinitionId: keyVaultSecretsUserRoleDefinitionId
    principalId: migrationPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource migrationStorageBlobDataContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroupName, storageAccountId, migrationPrincipalId, 'StorageBlobDataContributor')
  properties: {
    roleDefinitionId: storageBlobDataContributorRoleDefinitionId
    principalId: migrationPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource workerAcrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroupName, acrId, workerPrincipalId, 'AcrPull')
  properties: {
    roleDefinitionId: acrPullRoleDefinitionId
    principalId: workerPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource workerKeyVaultSecretsUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroupName, keyVaultId, workerPrincipalId, 'KeyVaultSecretsUser')
  properties: {
    roleDefinitionId: keyVaultSecretsUserRoleDefinitionId
    principalId: workerPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource workerStorageBlobDataContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroupName, storageAccountId, workerPrincipalId, 'StorageBlobDataContributor')
  properties: {
    roleDefinitionId: storageBlobDataContributorRoleDefinitionId
    principalId: workerPrincipalId
    principalType: 'ServicePrincipal'
  }
}
