#!/bin/sh
bundle exec htmlproofer ./_site --allow-hash-href --http-status-ignore 999
