# Zoe voice agent

This project is a small LangGraph-based voice agent that can run against Azure OpenAI or the standard OpenAI API. The main entry points (`main.py` and `src/agent/app.py`) load environment variables via `.env`, and the LangGraph course examples under `LangGraph-Course-freeCodeCamp/` can also use the OpenAI API.

## Quick start

1) Copy `.env.example` to `.env` and fill in the values below.  
2) (Optional) Create and activate a virtual environment.  
3) Install dependencies: `pip install -r requirements.txt`.  
4) Run the voice agent: `python main.py`.

The app will log which provider it found at startup. If Azure variables are fully set, Azure OpenAI is used; otherwise it falls back to the OpenAI API key.

## Environment variables

| Variable | Required | Purpose | How to get it |
| --- | --- | --- | --- |
| `AZURE_OPENAI_ENDPOINT` | Yes (Azure flow) | Base URL for your Azure OpenAI resource. | Azure Portal → Azure OpenAI resource → Resource Management → Keys and Endpoint → copy `Endpoint`. |
| `AZURE_OPENAI_API_KEY` | Yes (Azure flow) | API key used for Azure OpenAI calls. | Azure Portal → Azure OpenAI resource → Resource Management → Keys and Endpoint → copy `Key 1` or `Key 2`. |
| `AZURE_OPENAI_API_VERSION` | Yes (Azure flow) | API version passed to Azure OpenAI. | Use a supported version from the Azure OpenAI docs or the Playground “API version” dropdown (e.g., `2024-08-01-preview`). |
| `AZURE_OPENAI_DEPLOYMENT` | Yes (Azure flow) | Deployment name of your chat model. | Azure Portal → Azure OpenAI resource → Deployments → copy the `Deployment name` for your GPT-4o/compatible chat model. |
| `OPENAI_API_KEY` | Optional (OpenAI flow) | Standard OpenAI Platform key. Used if Azure is not fully configured, and by the LangGraph course scripts. | platform.openai.com → API keys → create and copy a secret key. |
| `OPENAI_MODEL` | Optional | OpenAI model name (defaults to `gpt-4o`). | Use a model your key can access, e.g., `gpt-4o-mini` or `gpt-4o`. |
| `MIC_INDEX` | Optional | Microphone device index for SpeechRecognition. | Leave blank to use the default input. To list devices: `python - <<'PY'\nimport speech_recognition as sr\nfor i, name in enumerate(sr.Microphone.list_microphone_names()):\n    print(i, name)\nPY`. |

The `.env` file lives in the repository root and is loaded automatically by `python-dotenv`. Keep your actual `.env` out of version control.
