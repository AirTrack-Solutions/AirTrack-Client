#!/usr/bin/env python3
"""
AirTrack Client Scheduler
scheduler.py

Runs Mangy Marmot on a 5-minute tick.
Marmot's own daily_schedule.json controls when code and registry updates
actually fire — this scheduler just keeps the heartbeat going.
"""
import logging
import sys

from apscheduler.schedulers.blocking import BlockingScheduler

sys.path.insert(0, "/app")
from woodland.mangy_marmot import main as marmot_main

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)

log = logging.getLogger(__name__)

scheduler = BlockingScheduler(timezone="Australia/Sydney")
scheduler.add_job(
    marmot_main,
    "interval",
    minutes=5,
    id="mangy_marmot",
    max_instances=1,
    coalesce=True,
)

log.info("AirTrack Client Scheduler starting — Mangy Marmot every 5 minutes.")

# Run immediately on startup, don't wait for first 5-minute tick
marmot_main()

scheduler.start()
