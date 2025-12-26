@description('The location for all resources.')
param location string = resourceGroup().location

@description('Prefix for resource names.')
param prefix string = 'docqa'

@description('The image for the API container.')
param apiImage string = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'

@description('The name of the database.')
param dbName string = 'docqa'

@description('The admin username for the Postgres server.')
param dbAdminLogin string = 'pgadmin'

@description('The admin password for the Postgres server.')
@secure()
param dbAdminPassword string

@description('The Vercel frontend URL for CORS.')
param vercelUrl string = ''

var logAnalyticsName = '${prefix}-logs'
var appInsightsName = '${prefix}-insights'
var containerAppEnvName = '${prefix}-env'
var searchName = '${prefix}-search'
var storageName = '${prefix}storage'
var postgresName = '${prefix}-db-server'
var apiAppName = '${prefix}-api'
var acrName = '${prefix}registry${uniqueString(resourceGroup().id)}' // must be globally unique

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

// --- Observability ---
resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: logAnalyticsName
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
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
  properties: {
    accessTier: 'Hot'
  }
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

resource postgresDb 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2022-12-01' = {
  parent: postgresServer
  name: dbName
}

// Allow Azure services to connect to Postgres
resource postgresFirewall 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2022-12-01' = {
  parent: postgresServer
  name: 'AllowAllAzureServices'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

// --- Container Apps ---
resource env 'Microsoft.App/managedEnvironments@2023-05-01' = {
  name: containerAppEnvName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
  }
}

resource apiApp 'Microsoft.App/containerApps@2023-05-01' = {
  name: apiAppName
  location: location
  properties: {
    managedEnvironmentId: env.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8000
      }
      registries: [
        {
          server: acr.properties.loginServer
          username: acr.listCredentials().username
          passwordSecretRef: 'acr-password'
        }
      ]
      secrets: [
        {
          name: 'db-url'
          value: 'postgresql+psycopg://${dbAdminLogin}:${dbAdminPassword}@${postgresServer.properties.fullyQualifiedDomainName}:5432/${dbName}?sslmode=require'
        }
        {
          name: 'search-key'
          value: searchService.listAdminKeys().primaryKey
        }
        {
          name: 'acr-password'
          value: acr.listCredentials().passwords[0].value
        }
      ]
    }
    template: {
      containers: [
        {
          image: apiImage
          name: 'api'
          env: [
            {
              name: 'DB_DATABASE_URL'
              secretRef: 'db-url'
            }
            {
              name: 'AZURE_SEARCH_ENDPOINT'
              value: 'https://${searchName}.search.windows.net'
            }
            {
              name: 'AZURE_SEARCH_API_KEY'
              secretRef: 'search-key'
            }
            {
              name: 'AZURE_SEARCH_INDEX'
              value: 'docqa-index-v3'
            }
            {
              name: 'DOCQA_ALLOWED_ORIGINS'
              value: 'http://localhost:3000,${vercelUrl}'
            }
          ]
        }
      ]
    }
  }
}

output apiFqdn string = apiApp.properties.configuration.ingress.fqdn
output acrLoginServer string = acr.properties.loginServer
output acrName string = acr.name
