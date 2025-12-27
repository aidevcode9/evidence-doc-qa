@description('The location for all resources.')
param location string = resourceGroup().location

@description('Prefix for resource names.')
param prefix string = 'docqa'

@description('The full Postgres connection string.')
@secure()
param dbDatabaseUrl string

@description('The Vercel frontend URL for CORS.')
param vercelUrl string = ''

// Unique suffix to avoid collisions between regions
var uniqueSuffix = uniqueString(resourceGroup().id, location)
var searchName = '${prefix}-search-${uniqueSuffix}'
var storageName = take('${prefix}stg${uniqueSuffix}', 24)
var acrName = take('${prefix}reg${uniqueSuffix}', 24)

// --- Existing Resources ---
var existingWebAppName = 'docqa'

// --- Container Registry ---
resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: acrName
  location: location
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: true
  }
}

// --- Search ---
resource searchService 'Microsoft.Search/searchServices@2023-11-01' = {
  name: searchName
  location: location
  sku: {
    name: 'basic'
  }
  properties: {
    replicaCount: 1
    partitionCount: 1
    hostingMode: 'default'
    semanticSearch: 'free'
  }
}

// --- Storage ---
resource storageAccount 'Microsoft.Storage/storageAccounts@2022-09-01' = {
  name: storageName
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2022-09-01' = {
  parent: storageAccount
  name: 'default'
}

resource container 'Microsoft.Storage/storageAccounts/blobServices/containers@2022-09-01' = {
  parent: blobService
  name: 'docqa-raw'
}

// --- Update Existing App Service Configuration ---
resource webApp 'Microsoft.Web/sites@2022-09-01' existing = {
  name: existingWebAppName
}

resource webAppConfig 'Microsoft.Web/sites/config@2022-09-01' = {
  parent: webApp
  name: 'appsettings'
  properties: {
    DOCKER_REGISTRY_SERVER_URL: 'https://${acr.properties.loginServer}'
    DOCKER_REGISTRY_SERVER_USERNAME: acr.listCredentials().username
    DOCKER_REGISTRY_SERVER_PASSWORD: acr.listCredentials().passwords[0].value
    DB_DATABASE_URL: dbDatabaseUrl
    AZURE_STORAGE_CONNECTION_STRING: 'DefaultEndpointsProtocol=https;AccountName=${storageAccount.name};AccountKey=${storageAccount.listKeys().keys[0].value};EndpointSuffix=${environment().suffixes.storage}'
    AZURE_STORAGE_CONTAINER: 'docqa-raw'
    AZURE_SEARCH_ENDPOINT: 'https://${searchName}.search.windows.net'
    AZURE_SEARCH_API_KEY: searchService.listAdminKeys().primaryKey
    AZURE_SEARCH_INDEX: 'docqa-index-v3'
    DOCQA_ALLOWED_ORIGINS: 'http://localhost:3000,${vercelUrl}'
    WEBSITES_PORT: '8000'
  }
}

output apiFqdn string = webApp.properties.defaultHostName
output webAppName string = webApp.name
output acrName string = acr.name
output acrLoginServer string = acr.properties.loginServer
