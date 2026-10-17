"""Independently audit the active calendar and refresh its timeline report.

Run: python3 scripts/recalculate_timeline.py
Required task hours come from estimate.json; dates use exact integer minutes.
"""
import json
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
START = date(2026, 12, 1)
DEADLINE = date(2027, 12, 31)
DAILY_MINUTES = 500
DAYS_OFF = {date(2026, 12, 31), date(2027, 1, 1), date(2027, 12, 31)}


def duration(minutes):
    hours, remainder = divmod(minutes, 60)
    return f'{hours:,}'.replace(',', ' ') + ' ч' + (f' {remainder} мин' if remainder else '')


def calendar_days(start, end):
    while start <= end:
        yield start
        start += timedelta(days=1)


def allocate(items):
    day, offset = START, 0
    stages, segments = [], []
    for item in items:
        parts = []
        for index, task in enumerate(item['tasks']):
            remaining = round(task['hours'] * 60)
            while remaining:
                if offset == DAILY_MINUTES:
                    day += timedelta(days=1)
                    offset = 0
                while day.weekday() == 6 or day in DAYS_OFF:
                    day += timedelta(days=1)
                take = min(DAILY_MINUTES - offset, remaining)
                parts.append({'date': day.isoformat(), 'stage': item['id'],
                              'task_index': index, 'minutes': take,
                              'day_offset_minutes': offset})
                offset += take
                remaining -= take
        assert sum(p['minutes'] for p in parts) == round(item['base'] * 60)
        stages.append({'id': item['id'], 'title': item['title'], 'track': item['track'],
                       'hours': item['base'], 'start': parts[0]['date'], 'end': parts[-1]['date']})
        segments.extend(parts)
    return {'total_minutes': sum(p['minutes'] for p in segments),
            'finish': stages[-1]['end'], 'stages': stages, 'segments': segments}


def main():
    source = json.loads((ROOT / 'estimate.json').read_text())
    schedule = json.loads((ROOT / 'schedule.json').read_text())
    items = [source['items'][key] for key in source['order']
             if source['items'][key]['track'] not in {'reserve', 'capacity'}]
    core = allocate(items)
    categories = {name: sum(round(task[name] * 60) for item in items for task in item['tasks'])
                  for name in ('learn', 'build', 'verify')}
    assert sum(categories.values()) == core['total_minutes']
    capacity, allocated = defaultdict(int), defaultdict(int)
    for day in calendar_days(START, DEADLINE):
        if day.weekday() < 6 and day not in DAYS_OFF:
            capacity[day.strftime('%Y-%m')] += DAILY_MINUTES
    for part in core['segments']:
        allocated[part['date'][:7]] += part['minutes']
    buffer_minutes = sum(capacity.values()) - core['total_minutes']

    # Compare every independently computed task slice with the active calendar.
    actual = [{'date': p['date'], 'stage': p['item'], 'task_index': p['task'],
               'minutes': p['minutes'], 'day_offset_minutes': p['day_offset_minutes']}
              for p in schedule['segments'] if p['item'] != 'CAP']
    assert actual == core['segments'], 'Active calendar differs from recalculation'
    assert schedule['start'] == str(START) and schedule['deadline'] == str(DEADLINE)
    assert schedule['daily_minutes'] == DAILY_MINUTES and schedule['weekly_hours'] == 50
    assert schedule['work_finish'] == core['finish'] <= str(DEADLINE)
    assert schedule['calendar_capacity_minutes'] == sum(capacity.values())
    assert schedule['allocated_minutes'] == core['total_minutes']
    assert schedule['buffer_minutes'] == buffer_minutes >= 0
    for month in schedule['months']:
        key = f"{month['year']}-{month['month']:02}"
        assert month['capacity_minutes'] == capacity[key]
        assert month['allocated_minutes'] == allocated[key]
    used = defaultdict(int)
    for part in core['segments']:
        assert date.fromisoformat(part['date']).weekday() < 6
        assert date.fromisoformat(part['date']) not in DAYS_OFF
        assert part['day_offset_minutes'] == used[part['date']]
        used[part['date']] += part['minutes']
        assert used[part['date']] <= DAILY_MINUTES

    report = {
        'status': 'verified_active_calendar', 'reviewed_on': '2026-10-17',
        'source': 'estimate.json', 'verified_calendar': 'schedule.json',
        'source_version': source['version'],
        'start': str(START), 'deadline': str(DEADLINE), 'weekly_hours': 50,
        'workdays': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'],
        'excluded_dates': sorted(map(str, DAYS_OFF)),
        'daily_minutes': DAILY_MINUTES, 'workday_count': sum(capacity.values()) // DAILY_MINUTES,
        'capacity_minutes': sum(capacity.values()), 'base_hours': core['total_minutes'] // 60,
        'category_minutes': categories, 'work_finish': core['finish'],
        'buffer_minutes': buffer_minutes,
        'assumptions': [
            'Equal 8 h 20 min workdays; Sunday off; 31 Dec 2026, 1 Jan 2027 and 31 Dec 2027 off; other holidays and vacation not deducted.',
            'Mandatory task hours, outcomes and execution order are unchanged.',
            'Selected reading and course study are already included in learning hours.',
            'Dates assume materials are ready and acceptance gates pass; delivery and unattended printing are elapsed time, not active work.',
            'One shared deadline buffer; reserve is not additional required study.',
        ],
        'months': [{'month': month, 'capacity_minutes': minutes,
                    'allocated_minutes': allocated[month],
                    'buffer_minutes': minutes - allocated[month]}
                   for month, minutes in capacity.items()],
        'core': core,
    }
    (ROOT / 'timeline-review.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    lines = [
        '# Пересчёт программы от 1 декабря 2026', '',
        'Расчёт проверен 17.10.2026. Отчёт соответствует текущему календарю schedule.json.', '',
        '**50 часов в неделю:** понедельник–суббота по 8 часов 20 минут; воскресенье — выходной. '
        '31.12.2026, 01.01.2027 и 31.12.2027 — выходные; прочие праздники и отпуск не вычтены. До 31.12.2027 включительно — '
        f'{report["workday_count"]} рабочих дней, {duration(report["capacity_minutes"])} доступного времени.', '',
        f'Обязательная программа: **{duration(core["total_minutes"])}** — изучение '
        f'{duration(categories["learn"])}, практика {duration(categories["build"])}, '
        f'проверка {duration(categories["verify"])}. Чтение и выбранные уроки курсов входят '
        'в эти часы. Содержание заданий и их порядок сохранены.', '',
        f'**Плановое завершение — {date.fromisoformat(core["finish"]):%d.%m.%Y}.** '
        f'До 31.12.2027 остаётся **{duration(buffer_minutes)}** общего запаса на задержки и переделки '
        f'({buffer_minutes / core["total_minutes"]:.1%} обязательной работы). '
        'Запас используется по необходимости и не отодвигает плановый финиш автоматически. '
        'R1–R4 обозначают направления риска без отдельных часов; их нельзя прибавлять к общему запасу.', '',
        'Даты предполагают прохождение приёмок и наличие деталей. Доставка, печать без участия '
        'человека и охлаждение занимают календарное время; их длительность не подтверждена. '
        'Пропуски и переделки расходуют запас и требуют обновления прогноза.', '',
        '## Этапы обязательной программы', '',
        '| Этап | Содержание | Часы | Начало | Окончание |', '|---|---|---:|---|---|',
    ]
    for stage in core['stages']:
        lines.append(f'| {stage["id"]} | {stage["title"]["ru"]} | {stage["hours"]} | '
                     f'{date.fromisoformat(stage["start"]):%d.%m.%Y} | {date.fromisoformat(stage["end"]):%d.%m.%Y} |')
    lines += ['', '## Помесячные часы', '',
              '| Месяц | Доступно | Обязательная работа | Запас |', '|---|---:|---:|---:|']
    for month in report['months']:
        lines.append(f'| {month["month"]} | {duration(month["capacity_minutes"])} | '
                     f'{duration(month["allocated_minutes"])} | {duration(month["buffer_minutes"])} |')
    lines += ['', 'Расчёт выполнен в целых минутах. Проверены часы каждого обязательного задания, '
              'совпадение всех отрезков с текущим календарём, отсутствие наложений, '
              'работы по воскресеньям и превышения дневного лимита. '
              'Детальный расчёт: [timeline-review.json](timeline-review.json).', '']
    (ROOT / 'timeline-review.md').write_text('\n'.join(lines))
    print(f'Validated {sum(len(item["tasks"]) for item in items)} tasks; '
          f'finish {core["finish"]}; buffer {duration(buffer_minutes)}.')


if __name__ == '__main__':
    main()
