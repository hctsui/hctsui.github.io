#!/usr/bin/env python3
"""Gate a 15-minute GitHub cron to one configured local-time daily rebuild."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / 'content/site.json'
STATE = ROOT / 'content/daily-update-state.json'


def check():
    from auto_update_ext import schedule_from_data
    config = json.loads(SITE.read_text(encoding='utf-8'))
    schedule = schedule_from_data(config)
    clock = datetime.now(ZoneInfo(schedule['timezone']))
    day = clock.date().isoformat()
    minutes = clock.hour * 60 + clock.minute
    hour, minute = map(int, schedule['time'].split(':'))
    state = json.loads(STATE.read_text(encoding='utf-8')) if STATE.exists() else {}
    # Once a day per local date; rerun after a failed run because marker is
    # written ONLY after successful builds and validations.
    manual = os.environ.get('FORCE_RUN', '').lower() == 'true'
    due = manual or (schedule['enabled'] and minutes >= 60*hour+minute and state.get('last_local_date') != day)
    print(f"Schedule: {schedule['timezone']} {schedule['time']} | now {clock.isoformat()} | due={due}")
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as f:
            f.write('run=' + str(due).lower() + '\n')
    if due and os.environ.get('GITHUB_ENV'):
        with open(os.environ['GITHUB_ENV'], 'a', encoding='utf-8') as f:
            f.write('SITE_TODAY=' + day + '\n')
            f.write('AUTO_UPDATE_LOCAL_DAY=' + day + '\n')
            f.write('AUTO_UPDATE_TIMEZONE=' + schedule['timezone'] + '\n')
    return due


def mark():
    day = os.environ.get('AUTO_UPDATE_LOCAL_DAY')
    timezone = os.environ.get('AUTO_UPDATE_TIMEZONE')
    if not day or not timezone:
        raise SystemExit('Missing local day/timezone from checked schedule')
    content = {
        'last_local_date': day,
        'timezone': timezone,
        'last_successful_build_utc': datetime.now(ZoneInfo('UTC')).isoformat(),
    }
    STATE.write_text(json.dumps(content, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print('Marked successful daily rebuild: ' + day)


if __name__ == '__main__':
    if len(sys.argv) != 2 or sys.argv[1] not in ('check','mark'):
        raise SystemExit('Usage: python3 tools/daily_update_schedule.py check|mark')
    check() if sys.argv[1] == 'check' else mark()
