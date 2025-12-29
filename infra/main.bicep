param searchServiceEndpoint string
param searchServiceApiKey string
param webAppName string = 'docqa'
param vercelUrl string = ''
param databaseUrl string
param metricsAdminToken string = ''

resource webApp 'Microsoft.Web/sites@2022-09-01' existing = {
  name: webAppName
}

resource appSettings 'Microsoft.Web/sites/config@2022-09-01' = {
  name: '${webApp.name}/appsettings'
  properties: {
    DATABASE_URL: databaseUrl
    APP_MODULE: 'app.main:app'
    WEBSITES_PORT: '8000'
    AZURE_SEARCH_ENDPOINT: searchServiceEndpoint
    AZURE_SEARCH_API_KEY: searchServiceApiKey
    METRICS_ADMIN_TOKEN: metricsAdminToken
    SCM_DO_BUILD_DURING_DEPLOYMENT: 'true'
    DOCQA_ALLOWED_ORIGINS: 'http://localhost:3000,${vercelUrl}'
  }
}

resource siteConfig 'Microsoft.Web/sites/config@2022-09-01' = {
  name: '${webApp.name}/web'
  properties: {
    linuxFxVersion: 'PYTHON|3.12'
    appCommandLine: 'bash /home/site/wwwroot/startup.sh'
  }
}

output webAppName string = webApp.name
