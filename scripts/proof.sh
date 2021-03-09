#!/bin/sh
set -x
bundle exec htmlproofer ./_site --allow-hash-href --http-status-ignore 403,999
