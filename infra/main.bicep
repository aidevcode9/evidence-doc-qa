param searchServiceEndpoint string
param searchServiceApiKey string
param storageAccountName string = 'docqastor${uniqueString(resourceGroup().id)}'
param appServicePlanName string = 'docqa-plan'
param webAppName string = 'docqa-api-${uniqueString(resourceGroup().id)}'
param location string = resourceGroup().location
param vercelUrl string = ''
param databaseUrl string
param metricsAdminToken string = ''

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: storageAccountName
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    accessTier: 'Hot'
  }
}

resource appServicePlan 'Microsoft.Web/serverfarms@2022-09-01' = {
  name: appServicePlanName
  location: location
  sku: {
    name: 'B1'
    tier: 'Basic'
  }
  kind: 'linux'
  properties: {
    reserved: true
  }
}

resource webApp 'Microsoft.Web/sites@2022-09-01' = {
  name: webAppName
  location: location
  kind: 'app,linux'
  properties: {
    serverFarmId: appServicePlan.id
    siteConfig: {
      linuxFxVersion: 'PYTHON|3.12'
      appSettings: [
        {
          name: 'DATABASE_URL'
          value: databaseUrl
        }
        {
          name: 'APP_MODULE'
          value: 'app.main:app'
        }
        {
          name: 'WEBSITES_PORT'
          value: '8000'
        }
        {
          name: 'AZURE_SEARCH_ENDPOINT'
          value: searchServiceEndpoint
        }
        {
          name: 'AZURE_SEARCH_API_KEY'
          value: searchServiceApiKey
        }
        {
          name: 'METRICS_ADMIN_TOKEN'
          value: metricsAdminToken
        }
        {
          name: 'SCM_DO_BUILD_DURING_DEPLOYMENT'
          value: 'true'
        }
        {
          name: 'DOCQA_ALLOWED_ORIGINS'
          value: 'http://localhost:3000,${vercelUrl}'
        }
      ]
    }
  }
}

output webAppName string = webApp.name
