#!/bin/bash

mkdir -p /data/eka_lobby_harvester/code /data/eka_lobby_harvester/json
cd /data/eka_lobby_harvester/code

git clone -q https://github.com/argoroots/EKAlobby.git ./
git checkout -q master
git pull

printf "\n\n"
version=`date +"%y%m%d.%H%M%S"`
docker build --quiet --pull --tag=eka_lobby_harvester:$version ./ && docker tag eka_lobby_harvester:$version eka_lobby_harvester:latest

printf "\n\n"
docker stop eka_lobby_harvester
docker rm eka_lobby_harvester
docker run -d \
    --net="entu" \
    --name="eka_lobby_harvester" \
    --restart="always" \
    --cpu-shares=256 \
    --memory="250m" \
    --env="NODE_ENV=production" \
    --env="VERSION=$version" \
    --env="NEW_RELIC_APP_NAME=eka_lobby_harvester" \
    --env="NEW_RELIC_LICENSE_KEY=" \
    --env="NEW_RELIC_LOG=stdout" \
    --env="NEW_RELIC_LOG_LEVEL=error" \
    --env="NEW_RELIC_NO_CONFIG_FILE=true" \
    --env="ENTU_USER=" \
    --env="ENTU_KEY=" \
    --env="SENTRY_DSN=" \
    --volume="/data/eka_lobby_harvester/json:/usr/src/eka_lobby_harvester/json" \
    eka_lobby_harvester:latest

printf "\n\n"
