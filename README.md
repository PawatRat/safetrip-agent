# SafeTrip AI

SafeTrip AI is a tourist scam intake assistant for Thailand. It uses a
**supervisor (orchestrator) agent** that decides, every turn, which workers to
run, then composes one natural reply. The app runs as a single local service on
**http://127.0.0.1:8765** — the Python web demo serves the built React UI **and**
the agent backend together.

## Run (the only workflow)

Everything runs from this project folder. One service, one port.

```bash
# 1. Python env (first time only)
python3.11 -m venv .venv
.venv/bin/python -m pip install -e . pytest

# 2. Build the frontend bundle (Python serves this; no dev server)
cd frontend && npm install && npm run build && cd ..

# 3. Run the app
.venv/bin/python -m safetrip_agent.web_demo --port 8765 --env-file .env
```

Open **http://127.0.0.1:8765**.

- **Live mode** (default): needs live model credentials in `.env`. Gemini is the
  default provider, and Azure AI Foundry can be selected with
  `SAFETRIP_MODEL_PROVIDER=azure`.
- **Offline mode**: add `--offline` to use the deterministic fallback with no
  API key (used by the tests).

> Note: there is **no `npm run dev` / port 5173** anymore. The frontend is built
> with `npm run build` and served by the Python service on 8765. To see UI
> changes, rebuild (`npm run build`) and refresh.

### CLI (optional)

```bash
.venv/bin/python -m safetrip_agent.cli --message "Taxi driver overcharged me in Bangkok today."
```

`--interactive` for a chat loop, `--verbose` to print the pipeline, `--offline`
for the no-key path.

## Test

```bash
.venv/bin/python -m pytest tests/ -q
```

## Deploy to Azure Container Apps

The production deployment keeps the same one-service shape: one container serves
the built React UI and the `/api/*` backend on port `8765`.

### One-time Azure setup

Create the Azure resources. This subscription already has one Container Apps
environment in Southeast Asia, so the production app reuses that environment.

```bash
RG=rg-safetrip-ai-prod
LOCATION=southeastasia
ACR_NAME=acrsafetripaiprod
ENV_ID=/subscriptions/30d29718-2aba-4e7f-b052-078c15a6b42d/resourceGroups/rg-us01-poc/providers/Microsoft.App/managedEnvironments/us01-compliance-service-env
APP_NAME=ca-safetrip-ai-prod
IMAGE_NAME=safetrip-ai

az group create --name "$RG" --location "$LOCATION"
az acr create --resource-group "$RG" --name "$ACR_NAME" --sku Basic
ACR_LOGIN_SERVER=$(az acr show --name "$ACR_NAME" --query loginServer -o tsv)

az containerapp create \
  --name "$APP_NAME" \
  --resource-group "$RG" \
  --environment "$ENV_ID" \
  --image "mcr.microsoft.com/k8se/quickstart:latest" \
  --target-port 80 \
  --ingress external \
  --min-replicas 1 \
  --max-replicas 1

az containerapp identity assign --name "$APP_NAME" --resource-group "$RG" --system-assigned
PRINCIPAL_ID=$(az containerapp identity show --name "$APP_NAME" --resource-group "$RG" --query principalId -o tsv)
ACR_ID=$(az acr show --name "$ACR_NAME" --query id -o tsv)
az role assignment create --assignee "$PRINCIPAL_ID" --role AcrPull --scope "$ACR_ID"

az containerapp registry set \
  --name "$APP_NAME" \
  --resource-group "$RG" \
  --server "$ACR_LOGIN_SERVER" \
  --identity system

az containerapp ingress update \
  --name "$APP_NAME" \
  --resource-group "$RG" \
  --target-port 8765

az containerapp secret set \
  --name "$APP_NAME" \
  --resource-group "$RG" \
  --secrets gemini-api-key="<your-gemini-api-key>"

az containerapp update \
  --name "$APP_NAME" \
  --resource-group "$RG" \
  --set-env-vars \
    SAFETRIP_MODEL_PROVIDER=gemini \
    GEMINI_API_KEY=secretref:gemini-api-key
```

### Switching to Azure AI Foundry (Azure OpenAI)

Each agent runs at one of two **intelligence tiers** (low or high) — see
`AGENT_TIERS` in [model_provider.py](agents/safetrip_agent/model_provider.py).
The tier maps to a concrete model per provider, so swapping providers preserves
the high/low split (Gemini Flash↔Pro ≈ `gpt-5-mini`↔`gpt-5`). Azure GPT-5
reasoning effort is configured separately: low-tier agents default to `low`,
and high-tier agents default to `medium`.

Create two deployments in Foundry. The model IDs are `gpt-5-mini` and `gpt-5`;
the deployment names can match those model IDs, or you can use your own names
and set `SAFETRIP_AZURE_LOW_DEPLOYMENT` / `SAFETRIP_AZURE_HIGH_DEPLOYMENT`.
Then:

```bash
az containerapp secret set \
  --name "$APP_NAME" --resource-group "$RG" \
  --secrets azure-openai-key="<your-azure-openai-key>"

az containerapp update \
  --name "$APP_NAME" --resource-group "$RG" \
  --set-env-vars \
    SAFETRIP_MODEL_PROVIDER=azure \
    AZURE_OPENAI_ENDPOINT=https://<your-foundry>.openai.azure.com/ \
    AZURE_OPENAI_API_VERSION=2024-10-21 \
    SAFETRIP_AZURE_LOW_DEPLOYMENT=gpt-5-mini \
    SAFETRIP_AZURE_HIGH_DEPLOYMENT=gpt-5 \
    SAFETRIP_AZURE_LOW_REASONING_EFFORT=low \
    SAFETRIP_AZURE_HIGH_REASONING_EFFORT=medium \
    AZURE_OPENAI_API_KEY=secretref:azure-openai-key
```

Per-agent overrides (`SAFETRIP_DRAFTING_MODEL=<deployment-name>`) still win,
so you can A/B a single agent on a different deployment without touching code.
Per-agent reasoning overrides are also supported, for example
`SAFETRIP_DRAFTING_REASONING_EFFORT=high`.

The app intentionally uses `--max-replicas 1` because chat session state is
currently in memory inside the Python process. The first real SafeTrip image is
built and deployed by GitHub Actions after the secrets below are configured.

### GitHub Actions setup

Create an Entra application for GitHub OIDC and scope it to the resource group:

```bash
APP_ID=$(az ad app create --display-name safetrip-ai-github --query appId -o tsv)
az ad sp create --id "$APP_ID"
SUBSCRIPTION_ID=$(az account show --query id -o tsv)
TENANT_ID=$(az account show --query tenantId -o tsv)
ACR_ID=$(az acr show --name "$ACR_NAME" --query id -o tsv)

az role assignment create \
  --assignee "$APP_ID" \
  --role Contributor \
  --scope "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RG"

az role assignment create \
  --assignee "$APP_ID" \
  --role AcrPush \
  --scope "$ACR_ID"

az ad app federated-credential create \
  --id "$APP_ID" \
  --parameters '{
    "name": "github-main",
    "issuer": "https://token.actions.githubusercontent.com",
    "subject": "repo:PawatRat/safetrip-agent:ref:refs/heads/main",
    "audiences": ["api://AzureADTokenExchange"]
  }'
```

Set these GitHub repository secrets:

```text
AZURE_CLIENT_ID=$APP_ID
AZURE_TENANT_ID=$TENANT_ID
AZURE_SUBSCRIPTION_ID=$SUBSCRIPTION_ID
```

After this, every push to `main` runs tests, builds the frontend, builds and
pushes the Docker image to ACR, and updates the Container App.

### Validate deployment

```bash
FQDN=$(az containerapp show \
  --name ca-safetrip-ai-prod \
  --resource-group rg-safetrip-ai-prod \
  --query properties.configuration.ingress.fqdn \
  -o tsv)

curl "https://$FQDN/api/health"
curl "https://$FQDN/api/status"
```

## Architecture

A single LLM **Orchestrator** is the router. Workers are deterministic unless
judgment is genuinely required.

```text
user message
  -> ORCHESTRATOR (1 LLM call): intent + does the message carry case data?
       - confirm_submission (+pending draft) -> Submission Packet -> police endpoint
       - otherwise:
           [carries data] -> PERCEPTION (1 LLM call: classify + extract + evidence)
           -> COMPLETENESS (deterministic: required - collected)
           -> if ready: DRAFTING (LLM) -> GUIDANCE -> await confirmation
              else:     GUIDANCE -> SYNTHESIS (LLM: one natural reply)
       -> SAFETY (deterministic gate; LLM rewrite only if flagged)
  -> response
```

- **Perception** retrieves required evidence from the **Case & Evidence DB**
  (in-process vector index over `evidence_rules.py`).
- **Guidance** retrieves from the **Legal DB** (vector index over
  `legal_knowledge_base.py`).
- Retrieval is in `retrieval.py` — dependency-free, deterministic; authoritative
  outputs are unchanged, retrieval adds traceable provenance.

Per-turn LLM cost: recommendation/confirm ≈ 1 call, add info ≈ 2, draft ≈ 3
(down from ~6–7 in the earlier pipeline). Offline mode keeps every step
deterministic.

See `CLAUDE.md` for how the codebase is laid out and how to work in it.
