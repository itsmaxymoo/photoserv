#!/bin/bash

# Assuming you have docker compose aliased... Not dealing with docker compose vs docker-compose

docker compose --file docker-compose.dev.yml up
docker compose --file docker-compose.dev.yml down -v
docker compose --file docker-compose.dev.yml down -v