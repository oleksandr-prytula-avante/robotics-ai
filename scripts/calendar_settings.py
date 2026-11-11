"""Single calendar policy; effort estimates remain separate from available time."""
import json
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / 'calendar-config.json').read_text())
VERSION = CONFIG['version']
START = date.fromisoformat(CONFIG['start'])
DEADLINE = date.fromisoformat(CONFIG['deadline'])
DAILY_MINUTES = CONFIG['daily_minutes']
WORKDAYS = set(CONFIG['workdays'])
DAYS_OFF = {date.fromisoformat(day) for day in CONFIG['excluded_dates']}
WEEKLY_MINUTES = DAILY_MINUTES * len(WORKDAYS)
WEEKLY_HOURS = WEEKLY_MINUTES / 60
WEEK_START = START - timedelta(days=START.weekday())


def calendar_days():
    day = START
    while day <= DEADLINE:
        yield day
        day += timedelta(days=1)


def is_workday(day):
    return day.weekday() in WORKDAYS and day not in DAYS_OFF


def capacity_minutes():
    return sum(DAILY_MINUTES for day in calendar_days() if is_workday(day))


def as_hours(minutes):
    return minutes // 60 if minutes % 60 == 0 else minutes / 60


def duration_text(minutes, language='ru'):
    hours,rest = divmod(minutes,60)
    if language == 'ru':
        return f'{hours:,}'.replace(',',' ')+' ч'+(f' {rest} мин' if rest else '')
    return f'{hours:,} h'+(f' {rest} min' if rest else '')


def week_accounting():
    nominal = defaultdict(int)
    excluded = defaultdict(int)
    for day in calendar_days():
        week = (day-WEEK_START).days//7
        if day.weekday() in WORKDAYS:
            nominal[week] += DAILY_MINUTES
            if day in DAYS_OFF:
                excluded[week] += DAILY_MINUTES
    first,last = min(nominal),max(nominal)
    partial = {k for k,v in nominal.items() if v != WEEKLY_MINUTES}
    assert partial <= {first,last}
    return {
        'full_weeks': sum(v == WEEKLY_MINUTES for v in nominal.values()),
        'first_partial_week_minutes': nominal[first]-excluded[first] if first in partial else 0,
        'final_partial_week_minutes': nominal[last]-excluded[last] if last in partial and last != first else 0,
        'interior_excluded_minutes': sum(v for k,v in excluded.items() if k not in partial),
    }
