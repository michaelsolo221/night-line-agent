# Dialogflow CX Agent — Night Line

Agent definition in [JSON package export format](https://docs.cloud.google.com/dialogflow/cx/docs/reference/json-export). Every resource is a JSON file — no console drag-and-drop.

## Repository architecture

| Repo | Purpose |
|---|---|
| [`michaelsolo221/night-line-agent`](https://github.com/michaelsolo221/night-line-agent) (this repo) | Dialogflow CX agent definition — flows, pages, intents, webhooks. Agent-only files at root. |
| [`michaelsolo221/dgflow`](https://github.com/michaelsolo221/dgflow) | Cloud Run webhook app — TypeScript/Express orchestrator, persona loading, Gemini integration, Firestore memory. |

Why two repos: Dialogflow CX Git integration requires agent-only files at root and deletes non-agent files on push. The webhook app lives separately.

## Agent identity

- **Project:** `superb-tendril-409615`
- **Location:** `us-central1`
- **Agent ID:** `5c1fa4bf-24b8-4dc6-8de4-91da9aa7e165`
- **Console URL:** https://dialogflow.cloud.google.com/cx/projects/superb-tendril-409615/locations/us-central1/agents/5c1fa4bf-24b8-4dc6-8de4-91da9aa7e165

## Directory structure

```
agent.json                                      # agent settings, DTMF, start flow
generativeSettings/en.json                      # LLM model + safety settings
webhooks/
  night-line-orchestrator.json                  # Cloud Run webhook (ID Token auth)
intents/
  1/1.json + trainingPhrases/en.json            # DTMF "1"
  2/2.json + trainingPhrases/en.json            # DTMF "2"
  3/3.json + trainingPhrases/en.json            # DTMF "3"
  goodbye/goodbye.json + trainingPhrases/en.json
  Default Welcome Intent/                       # auto-created by CX
  Default Negative Intent/                      # auto-created by CX
flows/
  Default Start Flow/
    Default Start Flow.json                     # flow config, NLU settings
    pages/
      Start.json                                # welcome TTS + DTMF route to Luna
      Luna.json                                 # webhook greeting (persona=luna) -> Converse
      Converse.json                             # no-match -> webhook converse, no-input retry
      Goodbye.json                              # goodbye TTS
```

## Deploy

### Restore via REST API (one call)

```bash
cd night-line-agent && zip -r /tmp/agent.zip agent.json flows/ intents/ webhooks/ generativeSettings/

ACCESS_TOKEN=$(gcloud auth print-access-token)
curl -X POST \
  "https://us-central1-dialogflow.googleapis.com/v3/projects/superb-tendril-409615/locations/us-central1/agents/5c1fa4bf-24b8-4dc6-8de4-91da9aa7e165:restore" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "X-Goog-User-Project: superb-tendril-409615" \
  -H "Content-Type: application/json" \
  -d "{\"agentContent\": \"$(base64 -i /tmp/agent.zip)\"}"
```

### Console Git integration

1. Agent console -> **Manage** -> **Git** -> **Create new**
2. Repository: `https://github.com/michaelsolo221/night-line-agent.git`
3. Branch: `main`
4. Access token secret: `projects/superb-tendril-409615/secrets/github-token/versions/latest`
5. **Pull from Git** to restore

### Webhook auth (set after import)

The webhook auth (`serviceAgentAuth: ID_TOKEN`) is not preserved in JSON import. Set it in the console:
Open webhook -> Auth -> ID Token -> Save.

## Validation

```bash
python3 scripts/validate-agent.py      # local schema check
python3 scripts/validate-references.py  # cross-reference check
```

## Phone Gateway (manual, once)

Console -> Manage -> Integrations -> Dialogflow Phone Gateway -> Create
