param searchServiceName string = 'docqa-search-${uniqueString(resourceGroup().id)}'
param openAiResourceName string = 'docqa-openai-${uniqueString(resourceGroup().id)}'
param storageAccountName string = 'docqastor${uniqueString(resourceGroup().id)}'
param appServicePlanName string = 'docqa-plan'
param webAppName string = 'docqa-api-${uniqueString(resourceGroup().id)}'
param location string = resourceGroup().location
param vercelUrl string = ''

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

resource keyVault 'Microsoft.KeyVault/vaults@2023-02-01' = {
  name: 'docqa-kv-${uniqueString(resourceGroup().id)}'
  location: location
  properties: {
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: subscription().tenantId
    accessPolicies: []
    enabledForDeployment: true
    enabledForTemplateDeployment: true
    enabledForDiskEncryption: true
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
          name: 'DB_DATABASE_URL'
          value: '@Microsoft.KeyVault(SecretUri=${keyVault.properties.vaultUri}secrets/DB-DATABASE-URL/)'
        }
        {
          name: 'AZURE_SEARCH_ENDPOINT'
          value: 'https://${searchServiceName}.search.windows.net'
        }
        {
          name: 'AZURE_SEARCH_API_KEY'
          value: '@Microsoft.KeyVault(SecretUri=${keyVault.properties.vaultUri}secrets/AZURE-SEARCH-API-KEY/)'
        }
        {
          name: 'AZURE_OPENAI_ENDPOINT'
          value: 'https://${openAiResourceName}.openai.azure.com/'
        }
        {
          name: 'AZURE_OPENAI_API_KEY'
          value: '@Microsoft.KeyVault(SecretUri=${keyVault.properties.vaultUri}secrets/AZURE-OPENAI-API-KEY/)'
        }
        {
          name: 'AZURE_OPENAI_API_VERSION'
          value: '2024-02-15-preview'
        }
        {
          name: 'AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT'
          value: 'text-embedding-3-large'
        }
        {
          name: 'AZURE_STORAGE_CONNECTION_STRING'
          value: '@Microsoft.KeyVault(SecretUri=${keyVault.properties.vaultUri}secrets/AZURE-STORAGE-CONNECTION-STRING/)'
        }
        {
          name: 'DOCQA_METRICS_ADMIN_TOKEN'
          value: '@Microsoft.KeyVault(SecretUri=${keyVault.properties.vaultUri}secrets/DOCQA-METRICS-ADMIN-TOKEN/)'
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
      appCommandLine: 'python3 -m uvicorn apps.api.app.main:app --host 0.0.0.0 --port 8000 --log-level info'
    }
  }
}

output webAppName string = webApp.name
