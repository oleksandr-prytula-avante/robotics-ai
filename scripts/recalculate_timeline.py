"""Independently audit the active calendar and refresh its timeline report.

Run: python3 scripts/recalculate_timeline.py
Required task hours come from estimate.json; dates use exact integer minutes.
"""
import json
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from calendar_settings import CONFIG, START, DEADLINE, DAILY_MINUTES, DAYS_OFF, as_hours

ROOT = Path(__file__).resolve().parents[1]


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
        'status': 'verified_active_calendar', 'reviewed_on': '2026-11-11',
        'source': 'estimate.json', 'verified_calendar': 'schedule.json',
        'source_version': source['version'],
        'start': str(START), 'deadline': str(DEADLINE), 'weekly_hours': 50,
        'workdays': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'],
        'excluded_dates': sorted(map(str, DAYS_OFF)),
        'daily_minutes': DAILY_MINUTES, 'workday_count': sum(capacity.values()) // DAILY_MINUTES,
        'orientation': CONFIG['orientation'],
        'capacity_minutes': sum(capacity.values()), 'base_hours': as_hours(core['total_minutes']),
        'category_minutes': categories, 'work_finish': core['finish'],
        'buffer_minutes': buffer_minutes,
        'assumptions': [
            CONFIG['notes']['en'],
            'All 127 tasks have individual nominal estimates for the stated experience. New learning is not proportionally compressed; shared implementation and evidence reviews are reused.',
            'Routine debugging is included in implementation; no blanket allowance for unpredictable rework is added.',
            'Selected reading and course study are already included in learning hours.',
            'Dates assume materials are ready and acceptance gates pass; delivery and unattended printing are elapsed time, not active work.',
            'Retain all 701 learning hours and physical trials; 8 h 20 min removed from familiar setup, Python/replay and release organization for the 2027 calendar. No deadline buffer remains.',
        ],
        'months': [{'month': month, 'capacity_minutes': minutes,
                    'allocated_minutes': allocated[month],
                    'buffer_minutes': minutes - allocated[month]}
                   for month, minutes in capacity.items()],
        'core': core,
    }
    (ROOT / 'timeline-review.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    lines = [
        f'# Пересчёт программы: учёба с {START:%d.%m.%Y}', '',
        'Расчёт проверен 11.11.2026. Отчёт соответствует текущему календарю schedule.json и индивидуальной проверке всех 127 заданий.', '',
        '**2 января 2027 — ознакомление с планом, без учебных заданий. Учёба с понедельника, 4 января.**', '',
        '**50 часов в неделю:** понедельник–суббота по 8 часов 20 минут; воскресенье — выходной. '
        '31.12.2027 — рабочий день; прочие праздники и отпуск не вычтены. До 31.12.2027 включительно — '
        f'{report["workday_count"]} рабочих дней, {duration(report["capacity_minutes"])} доступного времени.', '',
        f'Обязательная программа: **{duration(core["total_minutes"])}** — изучение '
        f'{duration(categories["learn"])}, практика {duration(categories["build"])}, '
        f'проверка {duration(categories["verify"])}. Чтение и выбранные уроки курсов входят '
        'в эти часы. Новые темы не сокращаются пропорционально дедлайну. Оценка учитывает повторное использование знакомой программной работы, инструментов и готовых доказательств. '
        'Обычная отладка включена в реализацию; отдельный процент на непредсказуемые переделки не добавлен. Порядок заданий сохранён. '
        'Обоснование каждого задания: [task-hour-review.md](task-hour-review.md).', '',
        'Для сохранения 50 ч/неделю сняты **8 ч 20 мин** со знакомой подготовки среды, Python/воспроизведения записей и оформления общего выпуска. Все 701 ч изучения и физические испытания сохранены.', '',
        f'**Плановое завершение — {date.fromisoformat(core["finish"]):%d.%m.%Y}.** '
        f'До {DEADLINE:%d.%m.%Y} остаётся **{duration(buffer_minutes)}** общего запаса на задержки и переделки '
        f'({buffer_minutes / core["total_minutes"]:.1%} обязательной работы). '
        'Запаса нет: любой пропуск или переделка отодвигает плановый финиш. '
        'R1–R4 обозначают направления риска без отдельных часов; их нельзя прибавлять к общему запасу.', '',
        'Даты предполагают прохождение приёмок и наличие деталей. Доставка, печать без участия '
        'человека и охлаждение занимают календарное время; их длительность не подтверждена. '
        'Пропуски и переделки расходуют запас и требуют обновления прогноза.', '',
        '## Этапы обязательной программы', '',
        '| Этап | Содержание | Часы | Начало | Окончание |', '|---|---|---:|---|---|',
    ]
    for stage in core['stages']:
        lines.append(f'| {stage["id"]} | {stage["title"]["ru"]} | {duration(round(stage["hours"]*60))} | '
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
