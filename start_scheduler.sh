#!/bin/bash
# Start the CVE data ingestion scheduler

cd /home/avi/Downloads/thandev-github-starter/thandev/backend
source .venv/bin/activate
python scheduler.py
