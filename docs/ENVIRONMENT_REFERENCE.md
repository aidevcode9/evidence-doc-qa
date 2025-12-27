# Environment Variable Reference

This document serves as a human-readable reference for all configuration variables used in the DocQ&A project. 

**Note:** Always use UTF-8 encoding (no BOM) for the actual `.env` file.

## 1. Project Versions & Identity
| Variable | Description | Default/Value |
| :--- | :--- | :--- |
| `DOCQA_PROMPT_VERSION` | Version of LLM prompts. | `v3.1.0` |
| `DOCQA_RETRIEVAL_VERSION` | Version of retrieval logic. | `v3.1.0` |
| `DOCQA_INDEX_VERSION` | Version of the search index. | `v3.1.0` |
| `DOCQA_MODEL_ID` | Model identifier (e.g. `azure-openai`). | `azure-openai` |

## 2. Ingestion & Storage
| Variable | Description | Default/Value |
| :--- | :--- | :--- |
| `DOCQA_DATA_DIR` | Local data directory. | `data` |
| `DOCQA_PARSER_MODE` | PDF parsing mode (`tier0`, `tier1`). | `tier0` |
| `DOCQA_CHUNK_SIZE` | Size of text chunks (chars). | `900` |
| `DOCQA_CHUNK_OVERLAP` | Overlap between chunks (chars). | `150` |
| `AZURE_STORAGE_CONNECTION_STRING` | Azure Blob Storage connection string. | (Secret) |
| `AZURE_STORAGE_CONTAINER` | Azure Container name for PDFs. | `docqa-raw` |

## 3. Database & Search
| Variable | Description | Value |
| :--- | :--- | :--- |
| `DB_DATABASE_URL` | Postgres connection string. | (Secret) |
| `AZURE_SEARCH_ENDPOINT` | Azure AI Search Service URL. | (Secret) |
| `AZURE_SEARCH_API_KEY` | Azure AI Search Admin Key. | (Secret) |
| `AZURE_SEARCH_INDEX` | Azure AI Search Index Name. | `docqa-index-v3` |
| `AZURE_SEARCH_CREATE_INDEX` | Create index on startup if `1`. | `1` |
| `DOCQA_ENABLE_INDEXING` | Enable indexing pipeline if `1`. | `1` |

## 4. Embeddings & OpenAI
| Variable | Description | Value |
| :--- | :--- | :--- |
| `EMBEDDINGS_LOCAL` | Use hash-based local embeddings if `true`. | `true` |
| `EMBEDDINGS_MODE` | Embedding mode override (`local`/`remote`). | `local` |
| `EMBEDDINGS_DIM` | Dimensions of the embedding vector. | `3072` |
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI URL. | (Secret) |
| `AZURE_OPENAI_API_KEY` | Azure OpenAI Key. | (Secret) |
| `AZURE_OPENAI_API_VERSION` | Azure OpenAI API Version. | `2024-02-01` |
| `AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT` | Deployment name for embeddings. | `text-embedding-3-large` |

## 5. Retrieval Tuning
| Variable | Description | Value |
| :--- | :--- | :--- |
| `DOCQA_CONF_MIN` | Minimum confidence for answering. | `0.35` |
| `DOCQA_TOP_K` | Total results after RRF fusion. | `5` |
| `DOCQA_TOP_K_VECTOR` | Vector results before fusion. | `5` |
| `DOCQA_TOP_K_BM25` | Lexical results before fusion. | `5` |
| `DOCQA_RRF_K` | RRF constant for scoring. | `60` |

## 6. Security & Telemetry
| Variable | Description | Value |
| :--- | :--- | :--- |
| `DOCQA_ALLOWED_ORIGINS` | Comma-separated list for CORS. | `http://localhost:3000` |
| `DOCQA_METRICS_ADMIN_TOKEN` | Auth token for metrics endpoint. | (Optional) |
