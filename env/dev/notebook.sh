#!/bin/sh

docker run --rm -it \
    -p 8888:8888 \
    -e DOCKER_USER="$USER" \
    -v "$(dirname "$PWD")":/active \
    datasetdatabase_dev \
    bash -c "jupyter notebook"
