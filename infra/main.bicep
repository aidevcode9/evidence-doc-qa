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
var appServicePlanName = '${prefix}-plan-${uniqueSuffix}'
var webAppName = '${prefix}-api-${uniqueSuffix}'
var acrName = take('${prefix}reg${uniqueSuffix}', 24)

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

// --- App Service (Web App for Containers) ---
resource appServicePlan 'Microsoft.Web/serverfarms@2022-09-01' = {
  name: appServicePlanName
  location: location
  sku: {
    name: 'F1'
    tier: 'Free'
  }
  kind: 'linux'
  properties: {
    reserved: true
  }
}

resource webApp 'Microsoft.Web/sites@2022-09-01' = {
  name: webAppName
  location: location
  kind: 'app,linux,container'
  properties: {
    serverFarmId: appServicePlan.id
    siteConfig: {
      linuxFxVersion: 'DOCKER|${acr.properties.loginServer}/docqa-api:latest'
      appSettings: [
        {
          name: 'DOCKER_REGISTRY_SERVER_URL'
          value: 'https://${acr.properties.loginServer}'
        }
        {
          name: 'DOCKER_REGISTRY_SERVER_USERNAME'
          value: acr.listCredentials().username
        }
        {
          name: 'DOCKER_REGISTRY_SERVER_PASSWORD'
          value: acr.listCredentials().passwords[0].value
        }
        {
          name: 'DB_DATABASE_URL'
          value: 'postgresql+psycopg://${dbAdminLogin}:${dbAdminPassword}@${postgresServer.properties.fullyQualifiedDomainName}:5432/docqa?sslmode=require'
        }
        {
          name: 'AZURE_SEARCH_ENDPOINT'
          value: 'https://${searchName}.search.windows.net'
        }
        {
          name: 'AZURE_SEARCH_API_KEY'
          value: searchService.listAdminKeys().primaryKey
        }
        {
          name: 'AZURE_SEARCH_INDEX'
          value: 'docqa-index-v3'
        }
        {
          name: 'DOCQA_ALLOWED_ORIGINS'
          value: 'http://localhost:3000,${vercelUrl}'
        }
        {
          name: 'WEBSITES_PORT'
          value: '8000'
        }
      ]
    }
  }
}

output apiFqdn string = webApp.properties.defaultHostName
output webAppName string = webApp.name
output acrName string = acr.name
output acrLoginServer string = acr.properties.loginServer