#!/bin/sh
set -x
# Ignore URLs:
#   1. LinkedIn, because it requires signing in
#   2. IARC, because it just doesn't support HTTPS
bundle exec htmlproofer ./_site \
  --allow-hash-href \
  --http-status-ignore 403,999 \
  --check-external-hash=false \
  --ignore-urls "https://linkedin.com/in/christophebourquebedard,http://aerialroboticscompetition.org/"
