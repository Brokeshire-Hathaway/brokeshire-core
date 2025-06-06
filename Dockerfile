ARG PYTHON_BASE=3.12.6-bullseye

# Building phase for dependencies
FROM python:$PYTHON_BASE as builder
# Pin PDM version to ensure compatibility with the lock file
RUN pip install --upgrade pip && pip install pdm==2.15.4
WORKDIR /app
ENV PDM_CHECK_UPDATE false
COPY pyproject.toml pdm.lock ./
RUN pdm install --check --prod --no-editable

# Run slim
FROM python:$PYTHON_BASE
WORKDIR /app
COPY --from=builder /app/.venv/ .venv
ENV PATH "/app/.venv/bin:$PATH"
COPY brokeshire_agents brokeshire_agents
ENTRYPOINT ["uvicorn", "brokeshire_agents.main:app", "--host", "0.0.0.0", "--port",  "80"]
