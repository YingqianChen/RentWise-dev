"""Retry due, previously authorized local deletion jobs on this upload volume."""
import asyncio
import json

from app.services.file_cleanup_service import process_cleanup_jobs

if __name__ == '__main__':
    print(json.dumps(asyncio.run(process_cleanup_jobs())))
