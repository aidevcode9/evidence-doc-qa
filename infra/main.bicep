param searchServiceEndpoint string
param searchServiceApiKey string
param webAppName string = 'docqa'
param vercelUrl string = ''
param databaseUrl string
param metricsAdminToken string = ''
param azureOpenAiEndpoint string
param azureOpenAiApiKey string
param azureOpenAiApiVersion string
param azureOpenAiEmbeddingsDeployment string
param azureOpenAiChatEndpoint string
param azureOpenAiChatApiKey string
param azureOpenAiChatApiVersion string
param docqaModelId string

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
    AZURE_OPENAI_ENDPOINT: azureOpenAiEndpoint
    AZURE_OPENAI_API_KEY: azureOpenAiApiKey
    AZURE_OPENAI_API_VERSION: azureOpenAiApiVersion
    AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT: azureOpenAiEmbeddingsDeployment
    AZURE_OPENAI_CHAT_ENDPOINT: azureOpenAiChatEndpoint
    AZURE_OPENAI_CHAT_API_KEY: azureOpenAiChatApiKey
    AZURE_OPENAI_CHAT_API_VERSION: azureOpenAiChatApiVersion
    DOCQA_MODEL_ID: docqaModelId
    EMBEDDINGS_MODE: 'remote'
    EMBEDDINGS_LOCAL: 'false'
    METRICS_ADMIN_TOKEN: metricsAdminToken
    SCM_DO_BUILD_DURING_DEPLOYMENT: 'true'
    DOCQA_ALLOWED_ORIGINS: 'http://localhost:3000,${vercelUrl}'
  }
}

resource siteConfig 'Microsoft.Web/sites/config@2022-09-01' = {
  name: '${webApp.name}/web'
  properties: {
    linuxFxVersion: 'PYTHON|3.12'
    appCommandLine: 'bash -c "if [ -f /home/site/wwwroot/apps/api/startup.sh ]; then cd /home/site/wwwroot/apps/api && bash startup.sh; else cd /home/site/wwwroot && bash startup.sh; fi"'
  }
}

output webAppName string = webApp.name
