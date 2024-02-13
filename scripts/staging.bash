#!/usr/bin/env bash

scriptdir="$(dirname "$0")"
cd "$scriptdir"

docker compose -p ember-agents-staging -f ../docker/docker-compose.staging.yml up
