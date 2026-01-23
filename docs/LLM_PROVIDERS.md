# LLM Provider Setup Guide

This guide covers how to configure and use the different LLM providers supported by Evidence-Bound.

## Quick Start

Set the `LLM_PROVIDER` environment variable to choose your provider:

```bash
# Options: azure_openai (default), anthropic, gemini, ollama
LLM_PROVIDER=azure_openai
```

---

## Provider Comparison

| Provider | Latency | Cost | Quality | Air-Gap | Best For |
|----------|---------|------|---------|---------|----------|
| Azure OpenAI | Low | $$$ | Excellent | No | Enterprise with existing Azure |
| Anthropic Claude | Low | $$$ | Excellent | No | Best reasoning, legal analysis |
| Google Gemini | Very Low | $$ | Very Good | No | Cost-effective, high volume |
| Ollama (local) | Medium | Free | Good | Yes | On-prem, data sovereignty |

---

## 1. Azure OpenAI (Default)

**Best for:** Enterprise deployments with Azure infrastructure.

### Setup

1. Create an Azure OpenAI resource in the Azure Portal
2. Deploy a model (e.g., `gpt-4o`)
3. Get your endpoint and API key

### Configuration

```bash
LLM_PROVIDER=azure_openai

# Required
AZURE_OPENAI_CHAT_ENDPOINT=https://your-resource.openai.azure.com
AZURE_OPENAI_CHAT_API_KEY=your-api-key
MODEL_ID=gpt-4o  # Your deployment name

# Optional
AZURE_OPENAI_CHAT_API_VERSION=2024-02-15-preview
```

### Notes

- `MODEL_ID` is your **deployment name**, not the model name
- Supports GPT-4o, GPT-4 Turbo, GPT-3.5 Turbo
- Enterprise SLA and compliance certifications available

---

## 2. Anthropic Claude

**Best for:** Complex legal reasoning, nuanced analysis.

### Setup

1. Create an account at [console.anthropic.com](https://console.anthropic.com/)
2. Generate an API key
3. Add billing information

### Configuration

```bash
LLM_PROVIDER=anthropic

# Required
ANTHROPIC_API_KEY=sk-ant-api03-xxxxx

# Optional (defaults shown)
ANTHROPIC_MODEL=claude-sonnet-4-20250514
```

### Available Models

| Model | Speed | Quality | Cost | Notes |
|-------|-------|---------|------|-------|
| `claude-sonnet-4-20250514` | Fast | Excellent | $$ | **Recommended** - best balance |
| `claude-opus-4-20250514` | Slower | Best | $$$ | Highest capability |
| `claude-3-5-sonnet-20241022` | Fast | Excellent | $$ | Previous generation |
| `claude-3-5-haiku-20241022` | Very Fast | Good | $ | Cost-effective |

### Notes

- Excellent at following complex instructions
- Strong performance on legal document analysis
- 200K context window on most models

---

## 3. Google Gemini

**Best for:** Cost-effective deployments, fast response times.

### Setup

1. Go to [Google AI Studio](https://aistudio.google.com/apikey)
2. Create an API key
3. Enable the Generative AI API

### Configuration

```bash
LLM_PROVIDER=gemini

# Required
GEMINI_API_KEY=your-api-key

# Optional (defaults shown)
GEMINI_MODEL=gemini-2.0-flash
```

### Available Models

| Model | Speed | Quality | Cost | Notes |
|-------|-------|---------|------|-------|
| `gemini-2.0-flash` | Very Fast | Very Good | $ | **Recommended** - best value |
| `gemini-1.5-pro` | Fast | Excellent | $$ | Longer context (1M tokens) |
| `gemini-1.5-flash` | Very Fast | Good | $ | Balance of speed/quality |

### Notes

- Very competitive pricing
- Fast response times
- Good for high-volume workloads

---

## 4. Ollama (Local / On-Prem)

**Best for:** Air-gapped environments, data sovereignty, development.

### Setup

1. **Install Ollama**

   ```bash
   # macOS / Linux
   curl -fsSL https://ollama.ai/install.sh | sh

   # Windows
   # Download from https://ollama.ai/download
   ```

2. **Start the Ollama server**

   ```bash
   ollama serve
   # Server runs on http://localhost:11434
   ```

3. **Pull a model**

   ```bash
   # Recommended for most cases (16GB RAM)
   ollama pull llama3.2:8b

   # Alternative models
   ollama pull mistral:7b      # Fast, good reasoning
   ollama pull qwen2.5:7b      # Good for structured tasks
   ollama pull llama3.3:70b    # Best quality (needs 40GB+ VRAM)
   ```

### Configuration

```bash
LLM_PROVIDER=ollama

# Optional (defaults shown)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:8b
```

### Recommended Models for Legal/RAG

| Model | RAM Required | Quality | Speed | Use Case |
|-------|--------------|---------|-------|----------|
| `llama3.2:8b` | 16GB | Good | Fast | **General use** - best balance |
| `llama3.3:70b` | 40GB+ VRAM | Excellent | Slow | Complex legal reasoning |
| `mistral:7b` | 16GB | Good | Very Fast | Quick queries |
| `qwen2.5:7b` | 16GB | Good | Fast | Structured extraction |

### Remote Ollama Server

To use Ollama on a different machine:

```bash
# On the Ollama server, allow external connections
OLLAMA_HOST=0.0.0.0 ollama serve

# In your .env
OLLAMA_BASE_URL=http://ollama-server.internal:11434
```

### GPU Acceleration

Ollama automatically uses GPU if available:

- **NVIDIA**: Install CUDA drivers
- **Apple Silicon**: Metal acceleration automatic
- **AMD**: ROCm support (Linux only)

Check GPU usage:
```bash
ollama ps  # Shows running models and memory usage
```

### Notes

- No API costs - runs entirely locally
- Data never leaves your network
- Longer response times than cloud providers
- Quality varies by model size
- First request may be slow (model loading)

---

## Switching Providers

Switching providers requires only configuration changes:

```bash
# Development: Use Ollama (free, local)
LLM_PROVIDER=ollama
OLLAMA_MODEL=llama3.2:8b

# Production: Use Azure OpenAI (enterprise SLA)
LLM_PROVIDER=azure_openai
AZURE_OPENAI_CHAT_ENDPOINT=https://...
AZURE_OPENAI_CHAT_API_KEY=...
MODEL_ID=gpt-4o
```

No code changes required. The `get_llm_client()` factory function returns the appropriate client based on configuration.

---

## Testing Your Configuration

### Verify Provider Works

```bash
# Run the LLM provider tests
pytest tests/test_llm_providers.py -v

# Test a specific provider (requires credentials)
python -c "
from app.llm import get_llm_client
client = get_llm_client()
print(f'Provider: {client.provider}')
print(f'Model: {client.model}')
"
```

### Test with a Simple Query

```bash
# Start the API server
cd apps/api && uvicorn app.main:app --reload

# Make a test request
curl -X POST http://localhost:8000/v1/ask \
  -H "Content-Type: application/json" \
  -H "X-Tenant-Id: test-tenant" \
  -H "X-Matter-Id: test-matter" \
  -d '{"question": "What is 2+2?"}'
```

---

## Troubleshooting

### Azure OpenAI

| Error | Cause | Fix |
|-------|-------|-----|
| `401 Unauthorized` | Invalid API key | Check `AZURE_OPENAI_CHAT_API_KEY` |
| `404 Not Found` | Wrong endpoint or deployment | Verify `AZURE_OPENAI_CHAT_ENDPOINT` and `MODEL_ID` |
| `429 Too Many Requests` | Rate limit exceeded | Implement backoff or upgrade quota |

### Anthropic

| Error | Cause | Fix |
|-------|-------|-----|
| `401 Invalid API key` | Bad or expired key | Regenerate key at console.anthropic.com |
| `429 Rate limit` | Too many requests | Add delay between requests |
| `400 Bad request` | Invalid parameters | Check model name and parameters |

### Gemini

| Error | Cause | Fix |
|-------|-------|-----|
| `403 API key invalid` | Bad key or API not enabled | Enable Generative AI API in Google Cloud |
| `429 Rate limit` | Quota exceeded | Check quota at Google Cloud Console |
| `400 Bad request` | Invalid model or parameters | Verify model name |

### Ollama

| Error | Cause | Fix |
|-------|-------|-----|
| `Connection refused` | Ollama not running | Run `ollama serve` |
| `Model not found` | Model not pulled | Run `ollama pull <model>` |
| `Timeout` | Model too large / slow hardware | Use smaller model or increase timeout |
| `Out of memory` | Insufficient RAM/VRAM | Use smaller model or add memory |

---

## Security Considerations

### API Key Management

- Never commit API keys to version control
- Use environment variables or secrets managers
- Rotate keys periodically
- Use separate keys for dev/staging/production

### Ollama Security

- Ollama has no built-in authentication
- Don't expose Ollama to public internet
- Use firewall rules to restrict access
- Consider VPN for remote access

### Error Message Sanitization

All providers sanitize error messages to prevent API key leakage:

```python
# Gemini: API keys in error responses are redacted
"Gemini HTTP 400: [REDACTED]..."

# Ollama: Internal URLs are not exposed
"Cannot connect to Ollama server. Is Ollama running?"
```

---

## Environment Variable Reference

```bash
# === Provider Selection ===
LLM_PROVIDER=azure_openai  # azure_openai | anthropic | gemini | ollama

# === Azure OpenAI ===
AZURE_OPENAI_CHAT_ENDPOINT=https://your-resource.openai.azure.com
AZURE_OPENAI_CHAT_API_KEY=your-key
AZURE_OPENAI_CHAT_API_VERSION=2024-02-15-preview
MODEL_ID=gpt-4o

# === Anthropic ===
ANTHROPIC_API_KEY=sk-ant-xxx
ANTHROPIC_MODEL=claude-sonnet-4-20250514

# === Gemini ===
GEMINI_API_KEY=your-key
GEMINI_MODEL=gemini-2.0-flash

# === Ollama ===
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:8b
```
