#!/usr/bin/env python3
"""
Scheduler service for regular data ingestion
"""
import os
import sys
import time
import schedule
import logging
from datetime import datetime
from real_data_ingestion import main as run_ingestion

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
LOG = logging.getLogger(__name__)

def scheduled_ingestion():
    """Run the data ingestion process"""
    LOG.info("Starting scheduled CVE data ingestion")
    try:
        run_ingestion()
        LOG.info("Scheduled ingestion completed successfully")
    except Exception as e:
        LOG.error(f"Scheduled ingestion failed: {e}")

def main():
    """Main scheduler function"""
    LOG.info("Starting CVE data ingestion scheduler")
    
    # Schedule ingestion every 6 hours
    schedule.every(6).hours.do(scheduled_ingestion)
    
    # Also run once immediately on startup
    LOG.info("Running initial ingestion...")
    scheduled_ingestion()
    
    # Keep the scheduler running
    LOG.info("Scheduler started. Running every 6 hours...")
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute

if __name__ == "__main__":
    main()
