# Zoe voice agent

This project is a LangGraph-based voice agent that can run with Azure OpenAI, OpenAI, Claude (Anthropic), or Ollama.
The main entry points (`main.py` and `src/agent/app.py`) load environment variables from `.env`.

## Quick start

1. Copy `.env.example` to `.env`.
2. Fill in required values.
3. (Optional) Create and activate a virtual environment.
4. Install dependencies: `pip install -r requirements.txt`
5. Run the voice agent: `python main.py`

At startup, the app:
- Detects configured providers from `.env`
- Verifies each configured provider with a lightweight test call
- Prompts you to choose a provider when multiple verified providers are available
- Uses `LLM_PROVIDER` directly if you want to force a provider without prompting

## Environment variables

| Variable | Required | Purpose |
| --- | --- | --- |
| `AZURE_OPENAI_ENDPOINT` | Yes (Azure flow) | Azure OpenAI endpoint used by `AzureChatOpenAI`. |
| `AZURE_OPENAI_API_KEY` | Yes (Azure flow) | Azure OpenAI API key. |
| `AZURE_OPENAI_DEPLOYMENT` | Yes (Azure flow) | Azure deployment name for the chat model. |
| `AZURE_OPENAI_API_VERSION` | Yes (Azure flow) | API version for Azure OpenAI requests. |
| `OPENAI_API_KEY` | Yes (OpenAI flow) | Standard OpenAI key. |
| `OPENAI_MODEL` | Optional | OpenAI model name (default: `gpt-4o`). |
| `ANTHROPIC_API_KEY` | Yes (Claude flow) | Anthropic API key for Claude. |
| `CLAUDE_API_KEY` | Optional | Alias key name for Claude (used if `ANTHROPIC_API_KEY` is not set). |
| `CLAUDE_MODEL` | Optional | Claude model name (default: `claude-3-5-sonnet-latest`). |
| `LLM_PROVIDER` | Optional | Force provider and skip prompt. Values: `azure_openai`, `openai`, `claude`, `ollama`. |
| `AZURE_OPENAI_RESOURCE` | Optional | Azure resource name used by realtime/websocket flows. |
| `SESSIONS_URL` | Optional | Realtime sessions URL for ephemeral session key creation. |
| `WEBRTC_URL` | Optional | Realtime WebRTC URL for browser clients. |
| `AZURE_OPENAI_REALTIME_VOICE` | Optional | Realtime voice (example: `verse`). |
| `AZURE_OPENAI_REALTIME_OUTPUT_RATE` | Optional | Realtime output audio rate. |
| `AZURE_REALTIME_PLAYBACK_RATE` | Optional | Playback rate multiplier. |
| `GMAIL_CLIENT_ID` | Optional | Gmail OAuth client id (project metadata). |
| `GMAIL_CLIENT_SECRET` | Optional | Gmail OAuth client secret (project metadata). |
| `GMAIL_CREDENTIALS_FILE` | Optional | Path to OAuth credentials file (default: `credentials.json`). |
| `GMAIL_TOKEN_FILE` | Optional | Path to OAuth token cache file (default: `token.json`). |
| `GMAIL_TOKEN_BACKUP_FILE` | Optional | Path to token backup file before refresh/write (default: `token.json.bak`). |
| `OLLAMA_MODEL` | Optional | Local model setting used by local/Ollama paths. |
| `OLLAMA_BASE_URL` | Optional | Ollama host URL (default is local Ollama endpoint). |
| `OLLAMA_REASONING` | Optional | Toggle for local reasoning mode. |
| `MIC_INDEX` | Optional | Microphone device index for SpeechRecognition. |
| `TRIGGER_WORD` | Optional | Wake/trigger word for interactive flows. |
| `CONVERSATION_TIMEOUT` | Optional | Conversation timeout in seconds. |
| `USE_CONVERSATION_MEMORY` | Optional | Enable/disable conversation memory. |

## Token and GitHub safety

- `.env`, `token.json`, `token.json.bak`, and `credentials.json` are ignored by git.
- Use `.env.example` as the only committed template for environment config.
- `token.json` stores Gmail OAuth access/refresh tokens.
- `token.json.bak` stores the previous token content before overwrite/refresh.
