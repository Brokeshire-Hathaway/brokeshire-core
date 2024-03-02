#!/usr/bin/env bash

scriptdir="$(dirname "$0")"
cd "$scriptdir"

#
docker compose -p ember-core_development -f ../docker/docker-compose.development.yml stop
docker compose -p ember-core_development -f ../docker/docker-compose.development.yml up
