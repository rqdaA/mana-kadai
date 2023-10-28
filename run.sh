#!/bin/bash

IMG_NAME="mana-kadai"
PROG_LOC="/opt/mana-kadai"
if [ $(docker images $IMG_NAME | wc -l) -eq 1 ]; then
	docker build -t $IMG_NAME .
fi

docker run --rm --env-file "$PROG_LOC/.env" "$IMG_NAME"
