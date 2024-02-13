FROM python:3.11-bookworm

RUN curl -sSLO https://pdm-project.org/install-pdm.py && \
    curl -sSL https://pdm-project.org/install-pdm.py.sha256 | shasum -a 256 -c - && \
    python3 install-pdm.py -p /usr/local
