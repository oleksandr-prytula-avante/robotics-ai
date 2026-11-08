"""Rebuild the active calendar and its pages using exact integer minutes.

Run: python3 scripts/render_timeline.py
Required work is scheduled first; CAP is the remaining deadline buffer.
"""
import copy
import html
import json
import re
from collections import defaultdict
from datetime import date, timedelta
from html.parser import HTMLParser
from pathlib import Path
from render_timeline_infographic import update_homepage

ROOT = Path(__file__).resolve().parents[1]
START, DEADLINE = date(2028, 1, 2), date(2028, 12, 31)
WEEK_START = START - timedelta(days=START.weekday())
DAY_MINUTES = 500
DAYS_OFF = {date(2028, 12, 31)}

def is_workday(day):
    return day.weekday() < 6 and day not in DAYS_OFF

RU_MONTHS = 'Январь Февраль Март Апрель Май Июнь Июль Август Сентябрь Октябрь Ноябрь Декабрь'.split()
EN_MONTHS = 'January February March April May June July August September October November December'.split()


def bi(ru, en=None):
    if isinstance(ru, dict):
        ru, en = ru['ru'], ru['en']
    return f'<span lang="ru">{html.escape(ru)}</span><span lang="en">{html.escape(en)}</span>'


def hours(minutes):
    return minutes // 60 if minutes % 60 == 0 else minutes / 60


def amount(minutes):
    h, m = divmod(minutes, 60)
    return str(h) if not m else f'{h}:{m:02}'


def duration(minutes):
    h, m = divmod(minutes, 60)
    return bi(f'{h:,} ч'.replace(',', ' ') + (f' {m} мин' if m else ''),
              f'{h:,} h' + (f' {m} min' if m else ''))


def fmt(day):
    return date.fromisoformat(day).strftime('%d.%m.%Y')


def dates(item):
    return f'{fmt(item["start"])} — {fmt(item["end"])}'


def label(key):
    year, month = map(int, key.split('-'))
    return bi(f'{RU_MONTHS[month-1]} {year}', f'{EN_MONTHS[month-1]} {year}')


def stage_learning_hours(item):
    return sum(task.get('learn', 0) for task in item.get('tasks', []))


def update_reading_block(block, stage, by_id):
    hours_value = stage_learning_hours(by_id[stage])
    block = re.sub(r'Изучение на весь этап: \d+ ч', f'Изучение на весь этап: {hours_value} ч', block)
    block = re.sub(r'Learning for the complete stage: \d+ h', f'Learning for the complete stage: {hours_value} h', block)
    return block


class Elements(HTMLParser):
    """Locate balanced elements while preserving all unrelated source bytes."""
    VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}

    def __init__(self, source, predicate):
        super().__init__(convert_charrefs=False)
        self.source, self.predicate, self.stack, self.matches = source, predicate, [], []
        self.lines = [0]
        self.lines.extend(m.end() for m in re.finditer('\n', source))
        self.feed(source)

    def position(self):
        line, col = self.getpos()
        return self.lines[line-1] + col

    def handle_starttag(self, tag, attrs):
        if tag not in self.VOID:
            self.stack.append((tag, dict(attrs), self.position()))

    def handle_endtag(self, tag):
        if tag in self.VOID:
            return
        if not self.stack or self.stack[-1][0] != tag:
            raise ValueError(f'Unbalanced HTML at {self.getpos()}: {tag}')
        opened, attrs, start = self.stack.pop()
        end = self.source.index('>', self.position()) + 1
        if self.predicate(opened, attrs):
            self.matches.append((start, end, attrs))


def replace_elements(source, predicate, render):
    for start, end, attrs in sorted(Elements(source, predicate).matches, reverse=True):
        source = source[:start] + render(source[start:end], attrs) + source[end:]
    return source


def substitute(value, mapping):
    if isinstance(value, str):
        # Simultaneous replacement avoids replacing a newly inserted date twice.
        if mapping:
            return re.sub('|'.join(re.escape(k) for k in sorted(mapping, key=len, reverse=True)),
                          lambda m: mapping[m[0]], value)
        return value
    if isinstance(value, list):
        return [substitute(v, mapping) for v in value]
    if isinstance(value, dict):
        return {k: substitute(v, mapping) for k, v in value.items()}
    return value


def write_json(name, value):
    (ROOT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


SUMMARY = bi('30.12.2028 — завершение программы.', '30 December 2028 — programme completion.')
BUFFER = bi('До 31.12.2028 — свободного запаса нет.',
            'Through 31 December 2028 — no unallocated buffer remains.')
POLICY = bi('Старт 02.01.2028; первый рабочий день — 03.01.2028. Понедельник–суббота по 8 ч 20 мин, воскресенье свободно: 50 ч в неделю. '
            '31.12.2028 — выходной; прочие праздники и отпуск не вычтены. 2 600 ч обязательной работы завершаются 30.12.2028; календарь заполнен полностью. '
            'Чтобы сохранить все практические и проверочные результаты в 2028 году, 120 ч чтения и целевого изучения сняты диагностикой и зачётом уже подтверждённых навыков. '
            'Даты зависят от прохождения приёмок и наличия деталей; сроки поставок не подтверждены.',
            'Start 2 January 2028; the first workday is 3 January 2028. Monday–Saturday: 8 h 20 min per day; Sunday off, 50 h per week. '
            '31 December 2028 is a day off; other holidays and vacation are not deducted. The 2,600 h of required work finish on 30 December 2028; the calendar is fully allocated. '
            'To retain every practical and verification deliverable in 2028, 120 h of reading and targeted study are removed through diagnostics and credit for demonstrated skills. '
            'Dates depend on passed gates and available materials; supplier lead times are unconfirmed.')


def compress_learning(estimate, hours_to_remove=120):
    """Shorten only targeted learning time, preserving build and verification hours."""
    marker = estimate.get('timeline_compression', {})
    if marker.get('hours_removed') == hours_to_remove:
        return
    rows = []
    for key in estimate['order']:
        item = estimate['items'][key]
        if item.get('track') in {'reserve', 'capacity'}:
            continue
        for index, task in enumerate(item['tasks']):
            if task.get('learn', 0):
                rows.append((key, index, task['learn']))
    total = sum(learn for _, _, learn in rows)
    target = total - hours_to_remove
    exact = [learn * target / total for _, _, learn in rows]
    reduced = [int(value) for value in exact]
    for index in sorted(range(len(rows)), key=lambda i: exact[i] - reduced[i], reverse=True)[:target - sum(reduced)]:
        reduced[index] += 1
    for (key, task_index, _), learn in zip(rows, reduced):
        task = estimate['items'][key]['tasks'][task_index]
        task['learn'] = learn
        task['hours'] = learn + task['build'] + task['verify']
    for key in estimate['order']:
        item = estimate['items'][key]
        if item.get('track') not in {'reserve', 'capacity'}:
            item['base'] = sum(task['hours'] for task in item['tasks'])
            item['hours'] = item['base']
    estimate['timeline_compression'] = {
        'hours_removed': hours_to_remove,
        'category': 'learn',
        'method': 'diagnostics and credit for demonstrated skills; build and verification hours unchanged',
    }


def main():
    estimate = json.loads((ROOT / 'estimate.json').read_text())
    compress_learning(estimate)
    estimate['version'] = '4.5'
    previous = json.loads((ROOT / 'schedule.json').read_text())
    old_items = {x['id']: x for x in previous['items']}
    sources = {key: copy.deepcopy(estimate['items'][key]) for key in estimate['order']
               if estimate['items'][key]['track'] not in {'reserve', 'capacity'}}
    day, offset = START, 0
    items, all_parts = [], []
    capacity_minutes = sum(DAY_MINUTES for i in range((DEADLINE-START).days+1)
                           if is_workday(START+timedelta(days=i)))
    core_minutes = sum(x['base'] * 60 for x in sources.values())
    buffer_minutes = capacity_minutes - core_minutes
    assert core_minutes > 0 and buffer_minutes >= 0, 'Required work exceeds calendar capacity'
    if buffer_minutes:
        cap = copy.deepcopy(estimate['items']['CAP'])
        cap.update(base=hours(buffer_minutes), title={'ru': 'Запас на задержки и переделки до конца 2028',
                                                    'en': 'Buffer for delays and rework through 2028'})
        cap['tasks'] = [{'title': {'ru': 'Запас после завершения программы; это не обязательное задание.',
                                   'en': 'Buffer after programme completion; not a required task.'},
                         'hours': hours(buffer_minutes), 'minutes': buffer_minutes,
                         'learn': 0, 'build': 0, 'verify': 0, 'allocation_kind': 'capacity', 'refs': []}]
        sources['CAP'] = cap
    for key, source in sources.items():
        item = copy.deepcopy(source)
        item['hours'] = item['base']
        item['minutes'] = round(item['hours'] * 60)
        item['segments'] = []
        for index, task in enumerate(item['tasks']):
            remaining = round(task['hours'] * 60)
            task['segments'] = []
            while remaining:
                if offset == DAY_MINUTES:
                    day += timedelta(days=1)
                    offset = 0
                while not is_workday(day):
                    day += timedelta(days=1)
                take = min(DAY_MINUTES-offset, remaining)
                part = {'date': str(day), 'hours': hours(take), 'minutes': take,
                        'week': (day-WEEK_START).days // 7 + 1, 'item': key, 'task': index,
                        'day_offset': hours(offset), 'day_offset_minutes': offset}
                task['segments'].append(part)
                item['segments'].append(part)
                all_parts.append(part)
                remaining -= take
                offset += take
            task['start'], task['end'] = task['segments'][0]['date'], task['segments'][-1]['date']
        if item['segments']:
            item['start'], item['end'] = item['segments'][0]['date'], item['segments'][-1]['date']
        else:
            item['start'] = item['end'] = None
        items.append(item)
    by_id = {x['id']: x for x in items}
    assert by_id['G4']['end'] == '2028-12-30'
    mapping = {dates(old_items[key]): dates(value) for key, value in by_id.items() if key in old_items}

    old_policy = {
        '173 ч 20 мин': '88 ч 20 мин', '173 h 20 min': '88 h 20 min',
        '173:20': '88:20', '2 833:20': '2 808:20',
        '08.12.2027 — завершение': '18.12.2027 — завершение',
        '8 December 2027 — programme': '18 December 2027 — programme',
        'завершаются 08.12.2027': 'завершаются 18.12.2027',
        'заканчивается 08.12.2027': 'заканчивается 18.12.2027',
        'завершение программы — 8 декабря 2027': 'завершение программы — 18 декабря 2027',
        'programme completion 8 December 2027': 'programme completion 18 December 2027',
        'finish on 8 December 2027': 'finish on 18 December 2027',
        'finishes on 8 December 2027': 'finishes on 18 December 2027',
        'Отпуск и праздники не вычтены.': '31.12.2026, 01.01.2027 и 31.12.2027 — выходные; прочие праздники и отпуск не вычтены.',
        'Vacation and holidays are not deducted.': '31 December 2026, 1 January 2027 and 31 December 2027 are days off; other holidays and vacation are not deducted.',
        '133 ч 20 мин — 113 ч 20 мин': '48 ч 20 мин — 28 ч 20 мин',
        '133 h 20 min–113 h 20 min': '48 h 20 min–28 h 20 min',
    }
    mapping.update(old_policy)
    mapping.update({'2 660': '2 600', '2,660': '2,600', '2 720': '2 600', '2,720': '2,600',
                    '148 ч 20 мин': '0 ч', '148 h 20 min': '0 h', '148:20': '0:00',
                    '10.12.2027': '03.01.2028', '10 December 2027': '3 January 2028', '10 декабря 2027': '3 января 2028',
                    '2027 год': '2028 год', '2027 года': '2028 года', 'end of 2027': 'end of 2028',
                    'through the end of 2027': 'through the end of 2028',
                    'Что действительно входит в 2027 год': 'Что действительно входит в 2028 год',
                    'What is actually included in 2027': 'What is actually included in 2028',
                    'Свободная ёмкость до конца 2027': 'Свободная ёмкость до конца 2028',
                    'Unallocated capacity before the end of 2027': 'Unallocated capacity before the end of 2028',
                    'до конца 2027': 'до конца 2028', 'конца 2027': 'конца 2028', 'through 2027': 'through 2028',
                    'end-2027': 'end-2028', 'in 2027': 'in 2028',
                    'Why this plan fits within 2027': 'Why this plan fits within 2028',
                    'Что изменилось в плане 2027': 'Что изменилось в плане 2028',
                    'What changed in the 2027 plan': 'What changed in the 2028 plan',
                    'Основная программа 2027': 'Основная программа 2028', '2027 core': '2028 core',
                    'ОСНОВНОЙ МАРШРУТ · 2026—2027': 'ОСНОВНОЙ МАРШРУТ · 2028',
                    'CORE PATH · 2026–2027': 'CORE PATH · 2028', 'Маршрут · 2026—2027': 'Маршрут · 2028',
                    'The route · 2026–2027': 'The route · 2028',
                    'Редакция 4.3': 'Редакция 4.5', 'Revision 4.3': 'Revision 4.5',
                    'Старт 1 декабря 2026; завершение программы — 18 декабря 2027. Запас до 31 декабря — 0 ч.': 'Старт 2 января 2028; завершение программы — 30 декабря 2028. Запаса нет.',
                    'Start 1 December 2026; programme completion 18 December 2027. Buffer through 31 December: 0 h.': 'Start 2 January 2028; programme completion 30 December 2028. No buffer remains.',
                    '88 ч 20 мин': '0 ч', '88 h 20 min': '0 h',
                    '2026 / 2027': '2028', '17.10.2026': '19.10.2026', '17 October 2026': '19 October 2026'})

    # Material conditions occur in multiple reports and rendered task copies.
    assumptions = copy.deepcopy(estimate['calendar_assumptions'])
    for condition in assumptions['material_ready_conditions']:
        key, index = condition['stage'], condition['task_index']
        task = by_id[key]['tasks'][index]
        gate = by_id[key]['tasks'][0]
        old_text = copy.deepcopy(condition['condition'])
        local_map = {}
        for before, after in [(condition['nominal_slot_start'], task['start']),
                              (condition['nominal_gate_finish'], gate['end'])]:
            b, a = date.fromisoformat(before), date.fromisoformat(after)
            for pattern in ['%d.%m.%Y', '%d.%m', '%d %B %Y', '%d %B']:
                local_map[b.strftime(pattern)] = a.strftime(pattern)
            local_map[f'{b.day} {EN_MONTHS[b.month-1]} {b.year}'] = f'{a.day} {EN_MONTHS[a.month-1]} {a.year}'
            local_map[f'{b.day} {EN_MONTHS[b.month-1]}'] = f'{a.day} {EN_MONTHS[a.month-1]}'
        if key == 'L1':
            b, a = date.fromisoformat(old_items[key]['start']), date.fromisoformat(by_id[key]['start'])
            local_map[b.strftime('%d.%m.%Y')] = a.strftime('%d.%m.%Y')
            local_map[f'{b.day} {EN_MONTHS[b.month-1]} {b.year}'] = f'{a.day} {EN_MONTHS[a.month-1]} {a.year}'
        local_map.update({'85 ч': '0 ч', '85 h': '0 h',
                          '88 ч 20 мин': '0 ч', '88 h 20 min': '0 h',
                          '148 ч 20 мин': '0 ч', '148 h 20 min': '0 h',
                          '173 ч 20 мин': '0 ч', '173 h 20 min': '0 h'})
        condition['condition'] = substitute(old_text, local_map)
        condition['nominal_slot_start'], condition['nominal_gate_finish'] = task['start'], gate['end']
        for language in ('ru', 'en'):
            mapping[old_text[language]] = condition['condition'][language]
            mapping[html.escape(old_text[language])] = html.escape(condition['condition'][language])
    assumptions['explanation'] = {
        'ru': '50 ч в неделю: Пн–Сб по 8 ч 20 мин, Вс свободно. 31.12.2028 — выходной; прочие праздники и отпуск не вычтены. '
              'Обязательная работа заканчивается 30.12.2028, запас отсутствует. 120 ч чтения и целевого изучения сняты диагностикой; '
              'практика и проверка сохранены. Даты зависят от приёмок и получения деталей. Поставка, автономная печать и охлаждение '
              'требуют календарного времени; их отдельные длительности не зарезервированы.',
        'en': '50 h/week: Mon–Sat 8 h 20 min/day, Sunday off. 31 December 2028 is a day off; other holidays and vacation are not deducted. '
              'Required work finishes on 30 December 2028 with no remaining buffer. 120 h of reading and targeted study are removed through diagnostics; '
              'practical and verification work is retained. Dates depend on gates and material receipt. Shipping, unattended printing and cooling require elapsed time '
              'with no separate durations reserved.'}
    items = substitute(items, mapping)
    sources = substitute(sources, mapping)
    estimate = substitute(estimate, mapping)
    # Keep the old R1–R4 anchors as risk guidance, with no scheduled hours.
    for key in ['R1', 'R2', 'R3', 'R4']:
        estimate['items'][key].update(base=0, tasks=[], scheduled=False,
                                      note='Risk guidance only; uses the shared CAP buffer when needed.')
    estimate['items'].update(sources)
    estimate['items']['CAP'].update(
        base=0, hours=0, tasks=[],
        title={'ru': 'Запас на задержки и переделки до конца 2028',
               'en': 'Buffer for delays and rework through 2028'})
    estimate['order'] = list(sources)
    literature = json.loads((ROOT / 'literature.json').read_text())
    for key in estimate['order']:
        if key in literature.get('routes', {}):
            literature['routes'][key]['learn_hours'] = stage_learning_hours(estimate['items'][key])
    literature['learning_hours_total'] = sum(stage_learning_hours(estimate['items'][key]) for key in estimate['order'])
    write_json('literature.json', literature)
    month_parts = defaultdict(list)
    for part in all_parts:
        month_parts[part['date'][:7]].append(part)
    months = []
    for key, parts in month_parts.items():
        allocated = sum(p['minutes'] for p in parts if p['item'] != 'CAP')
        capacity = sum(p['minutes'] for p in parts)
        y, m = map(int, key.split('-'))
        months.append({'year': y, 'month': m, 'allocated_hours': hours(allocated),
                       'capacity_hours': hours(capacity), 'allocated_minutes': allocated,
                       'capacity_minutes': capacity, 'buffer_minutes': capacity-allocated,
                       'page': f'months/{key}.html'})
    workday_count = sum(1 for i in range((DEADLINE-START).days+1) if is_workday(START+timedelta(days=i)))
    calendar_fields = {'version': '4.5', 'start': str(START), 'deadline': str(DEADLINE),
                       'work_finish': by_id['G4']['end'], 'calendar_finish': items[-1]['end'],
                       'base_hours': core_minutes//60, 'allocated_hours': core_minutes//60,
                       'calendar_capacity_minutes': capacity_minutes, 'allocated_minutes': core_minutes,
                       'buffer_minutes': buffer_minutes, 'daily_minutes': DAY_MINUTES,
                       'weekly_hours': 50, 'week_start': str(WEEK_START),
                       'weeks': (DEADLINE-WEEK_START).days//7+1,
                       'full_weeks': capacity_minutes // (DAY_MINUTES * 6), 'first_partial_week_minutes': 0,
                       'excluded_dates': sorted(map(str, DAYS_OFF)),
                       'interior_excluded_minutes': 0,
                       'final_partial_week_minutes': capacity_minutes % (DAY_MINUTES * 6),
                       'final_partial_week_hours': hours(capacity_minutes % (DAY_MINUTES * 6)), 'calendar_assumptions': assumptions}
    schedule = {**calendar_fields, 'contingency_hours': 0, 'calendar_capacity_hours': hours(capacity_minutes),
                'unallocated_hours': hours(buffer_minutes), 'months': months, 'items': items, 'segments': all_parts}
    estimate.update(calendar_fields)
    estimate.update(reserve_hours=0, hours=hours(capacity_minutes), padding_hours=hours(buffer_minutes))
    write_json('estimate.json', estimate)
    write_json('schedule.json', schedule)

    pages = {p: substitute(p.read_text(), mapping) for p in list(ROOT.glob('*.html')) + list((ROOT/'months').glob('*.html'))}
    guides = {}
    for path, text in pages.items():
        if path.parent.name == 'months':
            for a, b, attrs in Elements(text, lambda t, a: t == 'details' and a.get('id', '').startswith('guide-')).matches:
                guides[attrs['id'][6:]] = text[a:b]
    by_id = {x['id']: x for x in items}
    for path, text in pages.items():
        if path.parent.name == 'months':
            continue
        # Refresh all shared navigation and stage date spans, preserving source archives.
        nav = ''.join(f'<a class="" href="{m["page"]}">{label(m["page"][7:14])}<small>{duration(m["allocated_minutes"])}</small></a>' for m in months)
        text = replace_elements(text, lambda t, a: t == 'div' and a.get('class') == 'month-links', lambda _s, _a: f'<div class="month-links">{nav}</div>')
        if path.name == 'curriculum.html':
            def curriculum_section(block, attrs):
                key = attrs.get('id')
                if key in ['R1', 'R2', 'R3', 'R4']:
                    title = estimate['items'][key]['title']
                    return f'<section class="module anchor" id="{key}"><span class="tag reserve">{key}</span><h2>{bi(title)}</h2><p>'+bi('Направление риска без отдельного блока в календаре. Запаса нет; при необходимости пересчитать срок.', 'Risk guidance without a separate calendar block. No buffer remains; reforecast if needed.')+'</p></section>'
                if key == 'CAP':
                    return f'<section class="module anchor" id="CAP"><h2>{bi({"ru": "Запас на задержки и переделки до конца 2028", "en": "Buffer for delays and rework through 2028"})}</h2><p>{BUFFER}</p></section>'
                return block
            text = replace_elements(text, lambda t, a: t == 'section' and a.get('id') in {'R1','R2','R3','R4','CAP'}, curriculum_section)
            def curriculum_task_row(block, attrs):
                stage, task_number = attrs['data-task'].rsplit('.', 1)
                task = by_id[stage]['tasks'][int(task_number) - 1]
                cells = [amount(round(task[key] * 60)) for key in ('learn', 'build', 'verify', 'hours')]
                return re.sub(r'(<td>.*?</td>)(?:<td>.*?</td>){4}',
                              lambda match: match.group(1) + ''.join(f'<td>{value}</td>' for value in cells),
                              block, count=1, flags=re.S)
            text = replace_elements(text, lambda t, a: t == 'tr' and 'data-task' in a,
                                    curriculum_task_row)
            text = replace_elements(text, lambda t, a: t == 'div' and 'data-reading-stage' in a,
                                    lambda block, attrs: update_reading_block(block, attrs['data-reading-stage'], by_id))
        if path.name == 'index.html':
            text = text.replace('<strong>2 960</strong>', '<strong>2 720</strong>').replace('<strong>14</strong>', '<strong>13</strong>')
            text = text.replace('часов: работа + резерв', 'часов обязательной работы').replace('hours: work + allowance', 'hours of required work')
            text = text.replace('Старт 1 ноября 2026; целевой срок — 31 декабря 2027.', 'Старт 2 января 2028; завершение программы — 30 декабря 2028. Запас отсутствует.')
            text = text.replace('Start 1 November 2026; target completion 31 December 2027.', 'Start 2 January 2028; programme completion 30 December 2028. No buffer remains.')
            def index_table(block, attrs):
                if 'months/2026-' not in block:
                    return block
                rows = []
                for month in months:
                    key = month['page'][7:14]
                    stage_ids = list(dict.fromkeys(p['item'] for p in month_parts[key]))
                    links = ', '.join(f'<a href="curriculum.html#{s}">{s}</a>' for s in stage_ids)
                    rows.append(f'<tr><td><a href="{month["page"]}">{label(key)}</a></td><td>{links}</td><td>{duration(month["allocated_minutes"])}</td><td>{duration(month["buffer_minutes"])}</td><td>{duration(month["capacity_minutes"])}</td></tr>')
                return '<table><thead><tr><th>'+bi('Месяц','Month')+'</th><th>'+bi('Этапы','Stages')+'</th><th>'+bi('Работа','Work')+'</th><th>'+bi('Запас','Buffer')+'</th><th>'+bi('Доступно','Capacity')+'</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table>'
            text = replace_elements(text, lambda t, a: t == 'table', index_table)
        if path.name == 'method.html':
            def method_row(block, attrs):
                if 'Separate allowance' in block:
                    return '<tr><td>'+bi('Запас до дедлайна','Buffer through deadline')+'</td><td>0</td><td>'+bi('Запаса нет; календарь заполнен полностью','No buffer; the calendar is fully allocated')+'</td></tr>'
                if 'Total planned' in block or ('Required programme' in block and ('<td>2 720</td>' in block or '<td>2 600</td>' in block)):
                    return '<tr><td>'+bi('Обязательная программа','Required programme')+'</td><td>2 600</td><td>30.12.2028</td></tr>'
                if 'Available capacity' in block or 'Доступное время' in block:
                    return '<tr><td>'+bi('Доступное время','Available capacity')+'</td><td>2 600:00</td><td>'+bi('312 рабочих дней; воскресенье свободно','312 workdays; Sunday off')+'</td></tr>'
                if re.search(r'curriculum.html#R[1-4]', block):
                    return re.sub(r'<td>\d+</td>', '<td>'+bi('Общий запас','Shared buffer')+'</td>', block)
                return block
            text = replace_elements(text, lambda t, a: t == 'tr', method_row)
        # Replace old calendar claims as complete bilingual paragraphs, not isolated
        # numbers that could also be prices, source citations or project effort.
        def calendar_paragraph(block, attrs):
            plain = html.unescape(re.sub('<[^>]+>', '', block))
            if ('40–60' in plain or '40–60' in block) and ('85' in plain or '2,960' in plain or '2 960' in plain):
                return '<p>'+bi('Опциональная плата хвоста не входит в 340 ч хвоста и 2 720 ч обязательной программы. Если добавить 40–60 ч, запас 88 ч 20 мин уменьшится до 48 ч 20 мин — 28 ч 20 мин; дату завершения нужно пересчитать. Изготовление и доставка требуют отдельного календарного времени.', 'The optional tail PCB is outside the tail’s 340 h and the required programme’s 2,720 h. Adding 40–60 h reduces the 88 h 20 min buffer to 48 h 20 min–28 h 20 min; reforecast completion. Fabrication and delivery require elapsed time.')+'</p>'
            if (re.search(r'\b85 (?:ч|h)\b|\b300 (?:ч|h)\b|3 045|3,045|Пн–Пт по 9|Mon–Fri 9|60 complete weeks|31\.12\.2026|31 December 2026|18\.12\.2027|18 December 2027', plain)
                    and not any(s in plain for s in ['Редакция 3', 'Revision 3', 'price', 'UAH'])):
                return '<p>'+POLICY+'</p>'
            return block.replace('2 960', '2 600').replace('2,960', '2,600').replace('2 720', '2 600').replace('2,720', '2,600')
        text = replace_elements(text, lambda t, a: t == 'p', calendar_paragraph)
        # A few pre-existing notices are divs rather than paragraphs.
        text = replace_elements(text, lambda t, a: t == 'div' and a.get('class') == 'note',
                                lambda b, a: '<div class="note">'+POLICY+'</div>' if re.search(r'85 ч|300 ч|3 045', re.sub('<p.*?</p>', '', b, flags=re.S)) else b)
        if path.name in {'index.html','method.html','changes.html'}:
            text = re.sub(r'<!-- timeline-summary -->.*?<!-- /timeline-summary -->', '', text, flags=re.S)
            text = text.replace('<main class="main">', '<main class="main"><!-- timeline-summary --><section class="note" id="timeline-summary"><p><strong>'+SUMMARY+'</strong></p><p>'+BUFFER+'</p><p>'+POLICY+'</p></section><!-- /timeline-summary -->', 1)
        text = text.replace('Основная программа · 4.3', 'Основная программа · 4.5').replace('Core programme · 4.3', 'Core programme · 4.5').replace('Основная программа · 4.4', 'Основная программа · 4.5').replace('Core programme · 4.4', 'Core programme · 4.5')
        text = re.sub(r'(?:months/\d{4}-\d{2}\.html)#guide-([A-Za-z0-9]+)',
                      lambda m: f'months/{by_id[m[1]]["start"][:7]}.html#guide-{m[1]}' if m[1] in by_id else f'curriculum.html#{m[1]}', text)
        # These notices use list items or a warning div rather than paragraphs.
        text = replace_elements(text, lambda t, a: t == 'div' and 'warning' in a.get('class', '').split(),
                                lambda b, a: '<div class="warning">'+POLICY+'</div>' if re.search(r'85 h|85 ч|31\.12\.2026|31 December 2026|18\.12\.2027|18 December 2027', b) else b)
        text = text.replace('300 ч резерва не превращаются', '88 ч 20 мин запаса не превращаются')
        text = text.replace('The 300 h allowance is not an extra book list.', 'The 88 h 20 min buffer is not an extra book list.')
        if path.name == 'growth.html':
            text = text.replace('2 960', '2 720').replace('2,960', '2,720')
        if path.name == 'changes.html':
            text = text.replace('<td>300</td><td>300</td><td>0</td>', '<td>300</td><td>0</td><td>−300</td>')
            text = text.replace('<td>4 155</td><td>2 960</td><td>−1 195</td>', '<td>4 155</td><td>2 720</td><td>−1 495</td>')
        if path.name == 'index.html':
            text = update_homepage(text, schedule, bi, duration, POLICY)
        if path.name == 'library.html':
            text = text.replace('<strong>645</strong>', '<strong>525</strong>').replace('645 ч изучения', '525 ч изучения').replace('645 learning hours', '525 learning hours')
            for key in estimate['order']:
                if key not in literature.get('routes', {}):
                    continue
                item = by_id[key]
                hours_value = stage_learning_hours(item)
                row_pattern = r'<tr><td><a href="curriculum.html#' + re.escape(key) + r'">.*?</td><td>.*?</td>'
                replacement = f'<tr><td><a href="curriculum.html#{key}">{key}</a> · {hours_value} {bi("ч", "h")}</td><td><a href="months/{item["start"][:7]}.html#guide-{key}">{fmt(item["start"])}</a></td>'
                text, _ = re.subn(row_pattern, replacement, text, count=1, flags=re.S)
        pages[path] = text

    # Reuse the existing stage reading/gate guides, then rebuild monthly task
    # parts from the calendar; each task outcome stays beside its actual week.
    template = pages[ROOT/'index.html']
    prefix = template.split('<main class="main">')[0] + '<main class="main">'
    prefix = prefix.replace('href="assets/', 'href="../assets/').replace('src="assets/', 'src="../assets/')
    prefix = re.sub(r'href="(?!https?:|#|\.\./)([^\"]+)"', r'href="../\1"', prefix)
    prefix = prefix.replace('class="active"', 'class=""')
    procurement = json.loads((ROOT/'procurement.json').read_text())
    for month_index, month in enumerate(months):
        key = month['page'][7:14]
        title_ru = f'{RU_MONTHS[month["month"]-1]} {month["year"]} · Robotics &amp; AI'
        title_en = f'{EN_MONTHS[month["month"]-1]} {month["year"]} · Robotics &amp; AI'
        head = re.sub(r'data-ru-title="[^"]*"', f'data-ru-title="{title_ru}"', prefix)
        head = re.sub(r'data-en-title="[^"]*"', f'data-en-title="{title_en}"', head)
        head = re.sub(r'<title>.*?</title>', f'<title>{title_en}</title>', head)
        stage_ids = list(dict.fromkeys(p['item'] for p in month_parts[key]))
        next_ids = [] if month_index == len(months)-1 else list(dict.fromkeys(p['item'] for p in month_parts[months[month_index+1]['page'][7:14]]))
        parts = [head, '<section class="hero"><h1>'+label(key)+'</h1><p>'+bi('Обязательная работа: ', 'Required work: ')+duration(month['allocated_minutes'])+' · '+bi('Запас: ', 'Buffer: ')+duration(month['buffer_minutes'])+'</p></section>', '<div class="note"><p>'+SUMMARY+'</p><p>'+BUFFER+'</p><p>'+POLICY+'</p></div>']
        parts.append('<section><h2>'+bi('Покупки и подготовка','Purchases and preparation')+'</h2>')
        for ids, title in [(stage_ids, bi('Используется в этом месяце','Used this month')), (next_ids, bi('Проверить поставку к следующему месяцу','Check supply for next month'))]:
            rows = [p for p in procurement['items'] if p['stage'] in ids and not p.get('optional')]
            parts.append('<h3>'+title+'</h3><ul>')
            for entry in rows:
                parts.append(f'<li><a href="../procurement.html#item-{entry["id"]}">{bi(entry["title"])}</a> · {entry["stage"]}</li>')
            if not rows:
                parts.append('<li>'+bi('Новых закупок по этапам нет.','No new stage purchases.')+'</li>')
            parts.append('</ul>')
        parts.append('</section>')
        weeks = defaultdict(list)
        for part in month_parts[key]:
            weeks[part['week']].append(part)
        for week, segments in weeks.items():
            parts.append(f'<h2 id="week-{week}">'+bi(f'Неделя {week}',f'Week {week}')+'</h2>')
            parts.append('<p>'+duration(sum(p['minutes'] for p in segments))+' · '+bi('часть недели в этом месяце','this month’s share of the week')+'</p>')
            groups = defaultdict(list)
            for part in segments:
                groups[(part['item'],part['task'])].append(part)
            parts.append('<div class="table-wrap"><table><thead><tr><th>'+bi('Этап / даты','Stage / dates')+'</th><th>'+bi('Задача и результат','Task and outcome')+'</th><th>'+bi('Время','Time')+'</th></tr></thead><tbody>')
            for (stage, index), task_parts in groups.items():
                task = by_id[stage]['tasks'][index]
                minutes = sum(p['minutes'] for p in task_parts)
                task_minutes = round(task['hours']*60)
                parts.append(f'<tr><td><a href="#guide-{stage}">{stage}</a><br>{fmt(task_parts[0]["date"])} — {fmt(task_parts[-1]["date"])}</td><td><div data-task="{stage}.{index+1}" data-part-minutes="{minutes}" data-total-minutes="{task_minutes}" data-part-hours="{hours(minutes)}" data-total-hours="{task["hours"]}">{bi(task["title"])}')
                for field in ['result', 'material_ready_condition']:
                    if task.get(field):
                        parts.append('<p class="small">'+bi(task[field])+'</p>')
                parts.append('<p class="small">'+bi('На этой странице: ','On this page: ')+duration(minutes)+' / '+duration(task_minutes)+'</p></div></td><td>'+duration(minutes)+'</td></tr>')
            parts.append('</tbody></table></div>')
        parts.append('<h2>'+bi('Инструкции для этапов этого месяца','Guidance for this month’s stages')+'</h2>')
        for stage in stage_ids:
            if stage == 'CAP':
                parts.append('<details id="guide-CAP"><summary>'+bi('Запас на задержки и переделки','Buffer for delays and rework')+'</summary><div><p>'+BUFFER+'</p></div></details>')
            else:
                assert stage in guides, stage
                parts.append(update_reading_block(guides[stage], stage, by_id))
        parts.append('<div class="panel"><h3>'+bi('Закрытие месяца','Month-end check')+'</h3><p>'+bi('Записать фактические часы, результаты и PASS/HOLD. Если работа задерживается, пересчитать прогноз; непройденные проверки не засчитывать.', 'Record actual hours, outcomes and PASS/HOLD. If work is delayed, reforecast completion; do not mark unmet gates as passed.')+'</p></div><div class="month-nav">')
        for neighbor in [month_index-1,month_index+1]:
            if 0 <= neighbor < len(months):
                target = months[neighbor]['page'][7:]
                parts.append(f'<a href="{target}">{label(target[:7])}</a>')
        parts.append('</div><footer>'+bi('Календарь 4.5 · 08.11.2026 · 50 ч/неделю.','Calendar 4.5 · 8 November 2026 · 50 h/week.')+'</footer></main></div></body></html>')
        pages[ROOT/month['page']] = '\n'.join(parts)
    # Keep old month URLs usable, but remove obsolete monthly assignments.
    active_month_paths = {ROOT / month['page'] for month in months}
    for old_path in (ROOT / 'months').glob('*.html'):
        if old_path not in active_month_paths:
            pages[old_path] = prefix + '<h1>'+bi('Календарь перенесён на 2028 год','Calendar moved to 2028')+'</h1><p>'+bi('Новый план начинается 02.01.2028; первый рабочий день — 03.01.2028.','The revised plan starts on 2 January 2028; the first workday is 3 January 2028.')+'</p><a href="2028-01.html">'+label('2028-01')+'</a></main></div></body></html>'
    for path, text in pages.items():
        path.write_text(text)
    procurement['baseline_hours_unchanged'] = core_minutes//60
    procurement['calendar_updated_on'] = '2026-11-08'
    write_json('procurement.json', procurement)
    print(f'Rendered {len(months)} months, {len(items)} stages; {by_id["G4"]["end"]} + {buffer_minutes} buffer minutes.')


if __name__ == '__main__':
    main()
