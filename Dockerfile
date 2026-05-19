FROM node:20-bookworm-slim AS frontend-build

WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build


FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml ./
COPY agents ./agents
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

RUN python -m pip install --upgrade pip \
    && python -m pip install -e .

EXPOSE 8765

CMD ["python", "-m", "safetrip_agent.web_demo", "--host", "0.0.0.0", "--port", "8765", "--env-file", "/dev/null"]
