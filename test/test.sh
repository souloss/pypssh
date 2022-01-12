#!/usr/bin/env sh
docker-compose up --scale sshd=1000 -d
