#!/bin/bash

IMG_NAME="mana-kadai"
if [ $(/usr/bin/docker images $IMG_NAME | wc -l) -eq 1 ]; then
	/usr/bin/docker build -t $IMG_NAME .
fi

/usr/bin/docker run --rm --env-file "$(pwd)/.env" -it "$IMG_NAME"
