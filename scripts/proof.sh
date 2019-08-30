#!/bin/sh
bundle exec htmlproofer ./_site --allow-hash-href --url-ignore *vimeo.com* --http-status-ignore 999
