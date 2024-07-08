#!/bin/bash

# Check the username and current time
if [ "$(whoami)" = "vagrant" ] && [ "$(date +%H)" -gt 12 ]; then
    echo "The username is 'vagrant' and the current time is after 12:00."
    exit 0  # Exit status 0 indicates success
else
    echo "The username is not 'vagrant' or the current time is before 12:00."
    exit 1  # Exit status 1 indicates failure
fi
