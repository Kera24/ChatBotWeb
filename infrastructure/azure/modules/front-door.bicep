param location string = 'global'
param namePrefix string
param environmentName string
param appHostName string
param apiHostName string
param widgetApiHostName string
param widgetHostName string
param cdnHostName string
param webContainerAppFqdn string
param apiContainerAppFqdn string
param widgetStaticHostName string
param tags object

var profileName = '${namePrefix}-${environmentName}-afd'
var endpointName = '${namePrefix}-${environmentName}-edge'

resource profile 'Microsoft.Cdn/profiles@2023-05-01' = {
  name: profileName
  location: location
  tags: tags
  sku: {
    name: 'Standard_AzureFrontDoor'
  }
  properties: {}
}

resource endpoint 'Microsoft.Cdn/profiles/afdEndpoints@2023-05-01' = {
  parent: profile
  name: endpointName
  location: location
  properties: {
    enabledState: 'Enabled'
  }
}

resource webOriginGroup 'Microsoft.Cdn/profiles/originGroups@2023-05-01' = {
  parent: profile
  name: 'web-origin-group'
  properties: {
    loadBalancingSettings: {
      sampleSize: 4
      successfulSamplesRequired: 3
      additionalLatencyInMilliseconds: 50
    }
    healthProbeSettings: {
      probePath: '/'
      probeRequestType: 'GET'
      probeProtocol: 'Https'
      probeIntervalInSeconds: 120
    }
  }
}

resource apiOriginGroup 'Microsoft.Cdn/profiles/originGroups@2023-05-01' = {
  parent: profile
  name: 'api-origin-group'
  properties: {
    loadBalancingSettings: {
      sampleSize: 4
      successfulSamplesRequired: 3
      additionalLatencyInMilliseconds: 50
    }
    healthProbeSettings: {
      probePath: '/health/live'
      probeRequestType: 'GET'
      probeProtocol: 'Https'
      probeIntervalInSeconds: 60
    }
  }
}

resource staticOriginGroup 'Microsoft.Cdn/profiles/originGroups@2023-05-01' = {
  parent: profile
  name: 'widget-static-origin-group'
  properties: {
    loadBalancingSettings: {
      sampleSize: 4
      successfulSamplesRequired: 3
      additionalLatencyInMilliseconds: 50
    }
    healthProbeSettings: {
      probePath: '/'
      probeRequestType: 'HEAD'
      probeProtocol: 'Https'
      probeIntervalInSeconds: 120
    }
  }
}

resource webOrigin 'Microsoft.Cdn/profiles/originGroups/origins@2023-05-01' = {
  parent: webOriginGroup
  name: 'web-container-app'
  properties: {
    hostName: webContainerAppFqdn
    httpPort: 80
    httpsPort: 443
    originHostHeader: webContainerAppFqdn
    priority: 1
    weight: 1000
    enabledState: 'Enabled'
    enforceCertificateNameCheck: true
  }
}

resource apiOrigin 'Microsoft.Cdn/profiles/originGroups/origins@2023-05-01' = {
  parent: apiOriginGroup
  name: 'api-container-app'
  properties: {
    hostName: apiContainerAppFqdn
    httpPort: 80
    httpsPort: 443
    originHostHeader: apiContainerAppFqdn
    priority: 1
    weight: 1000
    enabledState: 'Enabled'
    enforceCertificateNameCheck: true
  }
}

resource widgetStaticOrigin 'Microsoft.Cdn/profiles/originGroups/origins@2023-05-01' = {
  parent: staticOriginGroup
  name: 'widget-static-storage'
  properties: {
    hostName: widgetStaticHostName
    httpPort: 80
    httpsPort: 443
    originHostHeader: widgetStaticHostName
    priority: 1
    weight: 1000
    enabledState: 'Enabled'
    enforceCertificateNameCheck: true
  }
}

resource ruleSet 'Microsoft.Cdn/profiles/ruleSets@2023-05-01' = {
  parent: profile
  name: 'widgetDeliveryRules'
}

resource httpsRedirectRule 'Microsoft.Cdn/profiles/ruleSets/rules@2023-05-01' = {
  parent: ruleSet
  name: 'redirectHttps'
  properties: {
    order: 1
    conditions: [
      {
        name: 'RequestScheme'
        parameters: {
          typeName: 'DeliveryRuleRequestSchemeConditionParameters'
          operator: 'Equal'
          matchValues: [ 'HTTP' ]
          negateCondition: false
          transforms: []
        }
      }
    ]
    actions: [
      {
        name: 'UrlRedirect'
        parameters: {
          typeName: 'DeliveryRuleUrlRedirectActionParameters'
          redirectType: 'Moved'
          destinationProtocol: 'Https'
        }
      }
    ]
    matchProcessingBehavior: 'Stop'
  }
}

resource immutableCacheRule 'Microsoft.Cdn/profiles/ruleSets/rules@2023-05-01' = {
  parent: ruleSet
  name: 'immutableWidgetAssets'
  properties: {
    order: 2
    conditions: [
      {
        name: 'UrlPath'
        parameters: {
          typeName: 'DeliveryRuleUrlPathMatchConditionParameters'
          operator: 'RegEx'
          matchValues: [ '^/(widget-sdk/v[0-9]+\\.[0-9]+\\.[0-9][^/]*/|assets/).*$' ]
          negateCondition: false
          transforms: []
        }
      }
    ]
    actions: [
      {
        name: 'ModifyResponseHeader'
        parameters: {
          typeName: 'DeliveryRuleHeaderActionParameters'
          headerAction: 'Overwrite'
          headerName: 'Cache-Control'
          value: 'public, max-age=31536000, immutable'
        }
      }
      {
        name: 'ModifyResponseHeader'
        parameters: {
          typeName: 'DeliveryRuleHeaderActionParameters'
          headerAction: 'Overwrite'
          headerName: 'X-Content-Type-Options'
          value: 'nosniff'
        }
      }
    ]
    matchProcessingBehavior: 'Continue'
  }
}

resource aliasCacheRule 'Microsoft.Cdn/profiles/ruleSets/rules@2023-05-01' = {
  parent: ruleSet
  name: 'sdkMajorAliasCache'
  properties: {
    order: 3
    conditions: [
      {
        name: 'UrlPath'
        parameters: {
          typeName: 'DeliveryRuleUrlPathMatchConditionParameters'
          operator: 'RegEx'
          matchValues: [ '^/widget-sdk/v[0-9]+/loader\\.js$' ]
          negateCondition: false
          transforms: []
        }
      }
    ]
    actions: [
      {
        name: 'ModifyResponseHeader'
        parameters: {
          typeName: 'DeliveryRuleHeaderActionParameters'
          headerAction: 'Overwrite'
          headerName: 'Cache-Control'
          value: 'public, max-age=300, must-revalidate'
        }
      }
      {
        name: 'ModifyResponseHeader'
        parameters: {
          typeName: 'DeliveryRuleHeaderActionParameters'
          headerAction: 'Overwrite'
          headerName: 'X-Content-Type-Options'
          value: 'nosniff'
        }
      }
    ]
    matchProcessingBehavior: 'Continue'
  }
}

resource htmlCacheRule 'Microsoft.Cdn/profiles/ruleSets/rules@2023-05-01' = {
  parent: ruleSet
  name: 'iframeHtmlNoCache'
  properties: {
    order: 4
    conditions: [
      {
        name: 'UrlFileExtension'
        parameters: {
          typeName: 'DeliveryRuleUrlFileExtensionMatchConditionParameters'
          operator: 'Equal'
          matchValues: [ 'html' ]
          negateCondition: false
          transforms: []
        }
      }
    ]
    actions: [
      {
        name: 'ModifyResponseHeader'
        parameters: {
          typeName: 'DeliveryRuleHeaderActionParameters'
          headerAction: 'Overwrite'
          headerName: 'Cache-Control'
          value: 'no-cache, must-revalidate'
        }
      }
      {
        name: 'ModifyResponseHeader'
        parameters: {
          typeName: 'DeliveryRuleHeaderActionParameters'
          headerAction: 'Overwrite'
          headerName: 'Referrer-Policy'
          value: 'strict-origin-when-cross-origin'
        }
      }
    ]
    matchProcessingBehavior: 'Continue'
  }
}

resource webRoute 'Microsoft.Cdn/profiles/afdEndpoints/routes@2023-05-01' = {
  parent: endpoint
  name: 'web-route'
  dependsOn: [ webOrigin ]
  properties: {
    originGroup: {
      id: webOriginGroup.id
    }
    supportedProtocols: [ 'Http', 'Https' ]
    patternsToMatch: [ '/*' ]
    forwardingProtocol: 'HttpsOnly'
    linkToDefaultDomain: 'Enabled'
    httpsRedirect: 'Enabled'
    enabledState: 'Enabled'
    ruleSets: [
      { id: ruleSet.id }
    ]
  }
}

resource apiRoute 'Microsoft.Cdn/profiles/afdEndpoints/routes@2023-05-01' = {
  parent: endpoint
  name: 'api-route'
  dependsOn: [ apiOrigin ]
  properties: {
    originGroup: {
      id: apiOriginGroup.id
    }
    supportedProtocols: [ 'Http', 'Https' ]
    patternsToMatch: [ '/api/*', '/health/*', '/health' ]
    forwardingProtocol: 'HttpsOnly'
    linkToDefaultDomain: 'Enabled'
    httpsRedirect: 'Enabled'
    enabledState: 'Enabled'
    ruleSets: [
      { id: ruleSet.id }
    ]
  }
}

resource staticRoute 'Microsoft.Cdn/profiles/afdEndpoints/routes@2023-05-01' = {
  parent: endpoint
  name: 'widget-static-route'
  dependsOn: [ widgetStaticOrigin ]
  properties: {
    originGroup: {
      id: staticOriginGroup.id
    }
    supportedProtocols: [ 'Http', 'Https' ]
    patternsToMatch: [ '/*' ]
    forwardingProtocol: 'HttpsOnly'
    linkToDefaultDomain: 'Enabled'
    httpsRedirect: 'Enabled'
    enabledState: 'Enabled'
    ruleSets: [
      { id: ruleSet.id }
    ]
  }
}

output frontDoorProfileName string = profile.name
output frontDoorEndpointName string = endpoint.name
output frontDoorEndpointHostName string = endpoint.properties.hostName
output intendedCustomDomains object = {
  app: appHostName
  api: apiHostName
  widgetApi: widgetApiHostName
  widget: widgetHostName
  cdn: cdnHostName
}
