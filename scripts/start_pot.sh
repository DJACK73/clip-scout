#!/bin/sh
docker rm -f bgutil-pot >/dev/null 2>&1
docker run -d --name bgutil-pot --restart unless-stopped -m 512m -p 127.0.0.1:4416:4416 brainicism/bgutil-ytdlp-pot-provider
