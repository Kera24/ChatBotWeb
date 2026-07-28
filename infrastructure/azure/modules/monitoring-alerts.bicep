param location string
param namePrefix string
param environmentName string
param logAnalyticsWorkspaceId string
param applicationInsightsId string
param actionGroupEmailReceivers array = []
param actionGroupWebhookReceivers array = []
param apiHealthUrl string
param webUrl string
param widgetIframeUrl string
param sdkAliasUrl string
param tags object

var actionGroupName = '${namePrefix}-${environmentName}-ag-pilot-ops'
var alertSeverity = {
  critical: 1
  incident: 2
  warning: 3
}

resource actionGroup 'Microsoft.Insights/actionGroups@2023-01-01' = {
  name: actionGroupName
  location: 'global'
  tags: tags
  properties: {
    groupShortName: environmentName == 'pilot' ? 'pilotops' : 'stageops'
    enabled: true
    emailReceivers: actionGroupEmailReceivers
    webhookReceivers: actionGroupWebhookReceivers
  }
}

resource apiAvailability 'Microsoft.Insights/webtests@2022-06-15' = {
  name: '${namePrefix}-${environmentName}-avail-api-live'
  location: location
  tags: union(tags, { 'hidden-link:${applicationInsightsId}': 'Resource' })
  properties: {
    SyntheticMonitorId: '${namePrefix}-${environmentName}-avail-api-live'
    Name: '${namePrefix}-${environmentName} API live'
    Kind: 'standard'
    Enabled: true
    Frequency: 300
    Timeout: 30
    Locations: [ { Id: 'us-ca-sjc-azr' }, { Id: 'apac-hk-hkn-azr' } ]
    Request: { RequestUrl: apiHealthUrl, HttpVerb: 'GET' }
    ValidationRules: { ExpectedHttpStatusCode: 200, SSLCheck: true, SSLCertRemainingLifetimeCheck: 30 }
  }
}

resource webAvailability 'Microsoft.Insights/webtests@2022-06-15' = {
  name: '${namePrefix}-${environmentName}-avail-web'
  location: location
  tags: union(tags, { 'hidden-link:${applicationInsightsId}': 'Resource' })
  properties: {
    SyntheticMonitorId: '${namePrefix}-${environmentName}-avail-web'
    Name: '${namePrefix}-${environmentName} web'
    Kind: 'standard'
    Enabled: true
    Frequency: 300
    Timeout: 30
    Locations: [ { Id: 'us-ca-sjc-azr' }, { Id: 'apac-hk-hkn-azr' } ]
    Request: { RequestUrl: webUrl, HttpVerb: 'GET' }
    ValidationRules: { ExpectedHttpStatusCode: 200, SSLCheck: true, SSLCertRemainingLifetimeCheck: 30 }
  }
}

resource widgetAvailability 'Microsoft.Insights/webtests@2022-06-15' = {
  name: '${namePrefix}-${environmentName}-avail-widget-iframe'
  location: location
  tags: union(tags, { 'hidden-link:${applicationInsightsId}': 'Resource' })
  properties: {
    SyntheticMonitorId: '${namePrefix}-${environmentName}-avail-widget-iframe'
    Name: '${namePrefix}-${environmentName} widget iframe'
    Kind: 'standard'
    Enabled: true
    Frequency: 300
    Timeout: 30
    Locations: [ { Id: 'us-ca-sjc-azr' }, { Id: 'apac-hk-hkn-azr' } ]
    Request: { RequestUrl: widgetIframeUrl, HttpVerb: 'GET' }
    ValidationRules: { ExpectedHttpStatusCode: 200, SSLCheck: true, SSLCertRemainingLifetimeCheck: 30 }
  }
}

resource sdkAvailability 'Microsoft.Insights/webtests@2022-06-15' = {
  name: '${namePrefix}-${environmentName}-avail-sdk-v1'
  location: location
  tags: union(tags, { 'hidden-link:${applicationInsightsId}': 'Resource' })
  properties: {
    SyntheticMonitorId: '${namePrefix}-${environmentName}-avail-sdk-v1'
    Name: '${namePrefix}-${environmentName} SDK v1 alias'
    Kind: 'standard'
    Enabled: true
    Frequency: 300
    Timeout: 30
    Locations: [ { Id: 'us-ca-sjc-azr' }, { Id: 'apac-hk-hkn-azr' } ]
    Request: { RequestUrl: sdkAliasUrl, HttpVerb: 'GET' }
    ValidationRules: { ExpectedHttpStatusCode: 200, SSLCheck: true, SSLCertRemainingLifetimeCheck: 30 }
  }
}

resource publicApi5xxAlert 'Microsoft.Insights/scheduledQueryRules@2023-03-15-preview' = {
  name: '${namePrefix}-${environmentName}-alert-widget-public-api-5xx-spike'
  location: location
  tags: union(tags, { alert_id: 'widget-public-api-5xx-spike', runbook: 'docs/06_Operations/Widget_Incident_Response_Runbook.md' })
  properties: {
    displayName: 'Widget public API 5xx spike'
    severity: alertSeverity.critical
    enabled: true
    skipQueryValidation: true
    scopes: [ logAnalyticsWorkspaceId ]
    evaluationFrequency: 'PT5M'
    windowSize: 'PT10M'
    criteria: { allOf: [ { query: 'requests | where url has "/api/v1/widget/" | summarize failures=countif(resultCode startswith "5"), total=count() | extend failureRate=todouble(failures) / todouble(total) | where total >= 20 and failureRate > 0.05', timeAggregation: 'Count', operator: 'GreaterThan', threshold: 0 } ] }
    actions: { actionGroups: [ actionGroup.id ] }
  }
}

resource originDenialAlert 'Microsoft.Insights/scheduledQueryRules@2023-03-15-preview' = {
  name: '${namePrefix}-${environmentName}-alert-widget-origin-denial-spike'
  location: location
  tags: union(tags, { alert_id: 'widget-origin-denial-spike', runbook: 'docs/06_Operations/Widget_Operational_Runbook.md' })
  properties: {
    displayName: 'Widget origin denial spike'
    severity: alertSeverity.warning
    enabled: true
    skipQueryValidation: true
    scopes: [ logAnalyticsWorkspaceId ]
    evaluationFrequency: 'PT15M'
    windowSize: 'PT30M'
    criteria: { allOf: [ { query: 'traces | where message has "origin.validation.denied" or customDimensions.event_type has "origin.validation.denied" | summarize denials=count() | where denials > 25', timeAggregation: 'Count', operator: 'GreaterThan', threshold: 0 } ] }
    actions: { actionGroups: [ actionGroup.id ] }
  }
}

output actionGroupId string = actionGroup.id
output availabilityTestIds array = [ apiAvailability.id, webAvailability.id, widgetAvailability.id, sdkAvailability.id ]
