@description('The location for all resources.')
param location string = resourceGroup().location

@description('Prefix for resource names.')
param prefix string = 'docqa'

@description('The admin username for the Postgres server.')
param dbAdminLogin string = 'pgadmin'

@description('The admin password for the Postgres server.')
@secure()
param dbAdminPassword string

@description('The Vercel frontend URL for CORS.')
param vercelUrl string = ''

// Unique suffix to avoid collisions between regions
var uniqueSuffix = uniqueString(resourceGroup().id, location)
var searchName = '${prefix}-search-${uniqueSuffix}'
var storageName = take('${prefix}stg${uniqueSuffix}', 24)
var postgresName = '${prefix}-db-${uniqueSuffix}'
var acrName = take('${prefix}reg${uniqueSuffix}', 24)

// --- Existing Resources ---
// Using the details provided for the existing docqa web app
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

// --- Database (Postgres) ---
resource postgresServer 'Microsoft.DBforPostgreSQL/flexibleServers@2022-12-01' = {
  name: postgresName
  location: location
  sku: {
    name: 'Standard_B1ms'
    tier: 'Burstable'
  }
  properties: {
    administratorLogin: dbAdminLogin
    administratorLoginPassword: dbAdminPassword
    version: '15'
    storage: {
      storageSizeGB: 32
    }
  }
}

resource postgresFirewall 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2022-12-01' = {
  parent: postgresServer
  name: 'AllowAllAzureServices'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
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
    DB_DATABASE_URL: 'postgresql+psycopg://${dbAdminLogin}:${dbAdminPassword}@${postgresServer.properties.fullyQualifiedDomainName}:5432/docqa?sslmode=require'
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
