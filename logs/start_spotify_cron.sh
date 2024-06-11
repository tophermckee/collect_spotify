#!/bin/bash

LOG_FILE="$HOME/collect_spotify/logs/cron_logs.txt"
START_TIME=$(date +"%I:%M %p")
DATE=$(date +"%Y-%m-%d")

echo "download spotify cron starting at $START_TIME on $DATE" >> $LOG_FILE
