ARG PYTHON_BASE=3.12-bullseye

# Building phase for dependencies
FROM python:$PYTHON_BASE as builder
RUN curl https://sh.rustup.rs -sSf | bash -s -- -y && \
    pip install --upgrade pip && pip install -U pdm
ENV PATH "/root/.cargo/bin:${PATH}"
WORKDIR /app
ENV PDM_CHECK_UPDATE false
COPY pyproject.toml pdm.lock ./
RUN pdm install --check --prod --no-editable

# Run slim
FROM python:$PYTHON_BASE
WORKDIR /app
COPY --from=builder /app/.venv/ .venv
ENV PATH "/app/.venv/bin:$PATH"
COPY ember_agents ember_agents
ENTRYPOINT ["uvicorn", "ember_agents.main:app", "--host", "0.0.0.0", "--port",  "80"]
