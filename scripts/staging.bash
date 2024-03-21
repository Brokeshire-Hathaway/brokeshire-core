#!/usr/bin/env bash

#scriptdir="$(dirname "$0")"
#cd "$scriptdir"

docker compose -p ember-core_staging -f docker/docker-compose.staging.yml stop
docker compose -p ember-core_staging -f docker/docker-compose.staging.yml up -d
