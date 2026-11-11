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
from calendar_settings import CONFIG, VERSION, START, DEADLINE, DAILY_MINUTES, DAYS_OFF, WEEK_START, WEEKLY_HOURS, is_workday, week_accounting, duration_text
from render_learning import reading_route, foundation_path, reference_additions, library_stage_row, reference_card

ROOT = Path(__file__).resolve().parents[1]
DAY_MINUTES = DAILY_MINUTES

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


def update_reading_block(block, stage, by_id, literature, prefix=''):
    if stage not in literature['routes']:
        return block
    if block.startswith('<div') and 'data-reading-stage=' in block.split('>',1)[0]:
        return reading_route(stage,by_id[stage],literature,prefix)
    return replace_elements(block, lambda t,a: t == 'div' and a.get('data-reading-stage') == stage,
                            lambda _b,_a: reading_route(stage,by_id[stage],literature,prefix))


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


def calendar_messages(estimate, finish, buffer_minutes):
    tasks = [t for k in estimate['order'] for t in estimate['items'][k]['tasks']
             if estimate['items'][k]['track'] not in {'reserve','capacity'}]
    minutes = sum(round(t['hours']*60) for t in tasks)
    categories = {c:sum(round(t[c]*60) for t in tasks) for c in ('learn','build','verify')}
    end = date.fromisoformat(finish)
    summary = {'ru':f'{end:%d.%m.%Y} — завершение программы.', 'en':f'{end.day} {EN_MONTHS[end.month-1]} {end.year} — programme completion.'}
    buffer = {'ru':f'До {DEADLINE:%d.%m.%Y} — свободный запас {duration_text(buffer_minutes)}.',
              'en':f'Through {DEADLINE.day} {EN_MONTHS[DEADLINE.month-1]} {DEADLINE.year}: {duration_text(buffer_minutes,"en")} unallocated.'}
    policy = {
        'ru': f'2 января {START.year} — ознакомление с планом; учебные задания с понедельника, {START:%d.%m.%Y}. '
              f'Пн–Сб по 8 ч 20 мин, 50 ч в неделю; воскресенье свободно. 31 декабря {DEADLINE.year} — рабочий день; прочие праздники и отпуск не вычтены. '
              f'{duration_text(minutes)} обязательной работы завершаются {end:%d.%m.%Y}. '
              f'Изучение — {duration_text(categories["learn"])}, реализация — {duration_text(categories["build"])}, проверка — {duration_text(categories["verify"])}. '
              'Для сохранения 50 ч/неделю сняты 8 ч 20 мин знакомой подготовки среды, Python/записей и оформления выпуска; изучение новых тем и физические испытания сохранены. '
              'Даты зависят от приёмок и наличия деталей; отдельный процент на непредсказуемые переделки не добавлен.',
        'en': f'2 January {START.year}: programme orientation; study tasks start Monday {START.day} {EN_MONTHS[START.month-1]} {START.year}. '
              f'Mon–Sat at 8 h 20 min, 50 h/week; Sunday off. 31 December {DEADLINE.year} is a workday; other holidays and vacation are not deducted. '
              f'{duration_text(minutes,"en")} of required work finish on {end.day} {EN_MONTHS[end.month-1]} {end.year}. '
              f'Learning: {duration_text(categories["learn"],"en")}; implementation: {duration_text(categories["build"],"en")}; verification: {duration_text(categories["verify"],"en")}. '
              'Retain 50 h/week by removing 8 h 20 min of familiar setup, Python/replay and release organization; new learning and physical trials are retained. '
              'Dates depend on acceptance and materials; no blanket rework percentage is added.'}
    return summary,buffer,policy


def main():
    estimate = json.loads((ROOT / 'estimate.json').read_text())
    assert 'timeline_compression' not in estimate, 'Apply the individual task review first'
    estimate['version'] = VERSION
    previous = json.loads((ROOT / 'schedule.json').read_text())
    old_items = {x['id']: x for x in previous['items']}
    sources = {key: copy.deepcopy(estimate['items'][key]) for key in estimate['order']
               if estimate['items'][key]['track'] not in {'reserve', 'capacity'}}
    day, offset = START, 0
    items, all_parts = [], []
    capacity_minutes = sum(DAY_MINUTES for i in range((DEADLINE-START).days+1)
                           if is_workday(START+timedelta(days=i)))
    core_minutes = sum(round(t['hours']*60) for x in sources.values() for t in x['tasks'])
    buffer_minutes = capacity_minutes - core_minutes
    assert core_minutes > 0 and buffer_minutes >= 0, 'Required work exceeds calendar capacity'
    if buffer_minutes:
        cap = copy.deepcopy(estimate['items']['CAP'])
        cap.update(base=hours(buffer_minutes), title={'ru': f'Запас на задержки и переделки до конца {DEADLINE.year}',
                                                    'en': f'Buffer for delays and rework through {DEADLINE.year}'})
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
    assert by_id['G4']['end'] <= DEADLINE.isoformat()
    summary,buffer,policy = calendar_messages(estimate,by_id['G4']['end'],buffer_minutes)
    SUMMARY,BUFFER,POLICY = bi(summary),bi(buffer),bi(policy)
    mapping = {dates(old_items[key]): dates(value) for key, value in by_id.items() if key in old_items}
    prose_mapping = {}
    review = json.loads((ROOT / 'task-hour-review.json').read_text())
    # Update complete source prose, including copies in existing month guides.
    for key, item in by_id.items():
        if key not in old_items:
            continue
        for before, after in zip(old_items[key]['tasks'], item['tasks']):
            for field in ('title', 'result'):
                for language, value in before.get(field, {}).items():
                    target = after.get(field, {}).get(language)
                    if target and target != value:
                        prose_mapping[value] = target
                        prose_mapping[html.escape(value)] = html.escape(target)
        old_rationale = next((r.get('previous_stage_rationale') for r in review['tasks'] if r['stage'] == key), None)
        if old_rationale:
            for language, value in old_rationale.items():
                prose_mapping[value] = item['rationale'][language]
                prose_mapping[html.escape(value)] = html.escape(item['rationale'][language])

    # Current-year labels only: historical source files are never rewritten.
    old_years = {date.fromisoformat(previous['start']).year, 2028}
    for old_year in sorted(old_years - {START.year}):
        for ending in (' год',' года',' году'):
            prose_mapping[f'{old_year}{ending}'] = f'{START.year}{ending}'
        prose_mapping[f'конца {old_year}'] = f'конца {START.year}'
        for prefix in ('end of ', 'through ', 'in ', 'end-', 'Маршрут · ', 'The route · ', 'CORE PATH · ', 'ОСНОВНОЙ МАРШРУТ · '):
            prose_mapping[f'{prefix}{old_year}'] = f'{prefix}{START.year}'
        for title in ('Основная программа ', 'What is actually included in ', 'What changed in the ', 'Why this plan fits within '):
            prose_mapping[f'{title}{old_year}'] = f'{title}{START.year}'
        prose_mapping[f'{old_year} core'] = f'{START.year} core'
    for key,item in by_id.items():
        if key in old_items and old_items[key].get('rationale') and item.get('rationale'):
            for language,text in old_items[key]['rationale'].items():
                prose_mapping[text] = item['rationale'][language]
                prose_mapping[html.escape(text)] = html.escape(item['rationale'][language])

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
    assumptions['explanation'] = policy
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
        title={'ru': f'Запас на задержки и переделки до конца {DEADLINE.year}',
               'en': f'Buffer for delays and rework through {DEADLINE.year}'})
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
    calendar_fields = {'version': VERSION, 'start': str(START), 'deadline': str(DEADLINE),
                       'work_finish': by_id['G4']['end'], 'calendar_finish': items[-1]['end'],
                       'base_hours': hours(core_minutes), 'allocated_hours': hours(core_minutes),
                       'calendar_capacity_minutes': capacity_minutes, 'allocated_minutes': core_minutes,
                       'buffer_minutes': buffer_minutes, 'daily_minutes': DAY_MINUTES,
                       'weekly_hours': WEEKLY_HOURS, 'orientation': CONFIG['orientation'], 'week_start': str(WEEK_START),
                       'weeks': (DEADLINE-WEEK_START).days//7+1,
                       **week_accounting(),
                       'excluded_dates': sorted(map(str, DAYS_OFF)),
                       'final_partial_week_hours': hours(week_accounting()['final_partial_week_minutes']), 'calendar_assumptions': assumptions}
    schedule = {**calendar_fields, 'contingency_hours': 0, 'calendar_capacity_hours': hours(capacity_minutes),
                'unallocated_hours': hours(buffer_minutes), 'months': months, 'items': items, 'segments': all_parts}
    estimate.update(calendar_fields)
    estimate.update(reserve_hours=0, hours=hours(capacity_minutes), padding_hours=hours(buffer_minutes))
    write_json('estimate.json', estimate)
    write_json('schedule.json', schedule)

    pages = {p: substitute(p.read_text(), {**mapping, **prose_mapping})
             for p in list(ROOT.glob('*.html')) + list((ROOT/'months').glob('*.html'))}
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
                    return f'<section class="module anchor" id="CAP"><h2>{bi(estimate["items"]["CAP"]["title"])}</h2><p>{BUFFER}</p></section>'
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
                                    lambda block, attrs: update_reading_block(block, attrs['data-reading-stage'], by_id, literature))
        if path.name == 'index.html':
            text = text.replace('<strong>2 960</strong>', '<strong>2 720</strong>').replace('<strong>14</strong>', '<strong>13</strong>')
            text = text.replace('часов: работа + резерв', 'часов обязательной работы').replace('hours: work + allowance', 'hours of required work')
            def index_table(block, attrs):
                if 'class="roadmap' in block or not re.search(r'<a href="months/\d{4}-\d{2}\.html">',block) or 'Capacity' not in block:
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
                    return '<tr><td>'+bi('Обязательная программа','Required programme')+f'</td><td>{amount(core_minutes)}</td><td>{fmt(by_id["G4"]["end"])}</td></tr>'
                if 'Available capacity' in block or 'Доступное время' in block:
                    return '<tr><td>'+bi('Доступное время','Available capacity')+f'</td><td>{amount(capacity_minutes)}</td><td>'+bi(f'{workday_count} рабочих дней; воскресенье свободно',f'{workday_count} workdays; Sunday off')+'</td></tr>'
                if re.search(r'curriculum.html#R[1-4]', block):
                    return re.sub(r'<td>\d+</td>', '<td>'+bi('Общий запас','Shared buffer')+'</td>', block)
                return block
            text = replace_elements(text, lambda t, a: t == 'tr', method_row)
        # Replace old calendar claims as complete bilingual paragraphs, not isolated
        # numbers that could also be prices, source citations or project effort.
        def calendar_paragraph(block, attrs):
            plain = html.unescape(re.sub('<[^>]+>', '', block))
            if ('2028' in plain and ('Старт ' in plain or 'Start ' in plain)):
                return '<p>'+POLICY+'</p>'
            if ('40–60' in plain or '40–60' in block) and ('85' in plain or '2,960' in plain or '2 960' in plain):
                return '<p>'+bi('Опциональная плата хвоста не входит в 340 ч хвоста и 2 720 ч обязательной программы. Если добавить 40–60 ч, запас 88 ч 20 мин уменьшится до 48 ч 20 мин — 28 ч 20 мин; дату завершения нужно пересчитать. Изготовление и доставка требуют отдельного календарного времени.', 'The optional tail PCB is outside the tail’s 340 h and the required programme’s 2,720 h. Adding 40–60 h reduces the 88 h 20 min buffer to 48 h 20 min–28 h 20 min; reforecast completion. Fabrication and delivery require elapsed time.')+'</p>'
            if (re.search(r'\b85 (?:ч|h)\b|\b300 (?:ч|h)\b|3 045|3,045|Пн–Пт по 9|Mon–Fri 9|60 complete weeks|31\.12\.2026|31 December 2026|18\.12\.2027|18 December 2027', plain)
                    and not any(s in plain for s in ['Редакция 3', 'Revision 3', 'price', 'UAH'])):
                return '<p>'+POLICY+'</p>'
            return block
        text = replace_elements(text, lambda t, a: t == 'p', calendar_paragraph)
        # A few pre-existing notices are divs rather than paragraphs.
        text = replace_elements(text, lambda t, a: t == 'div' and a.get('class') == 'note',
                                lambda b, a: '<div class="note">'+POLICY+'</div>' if re.search(r'85 ч|300 ч|3 045', re.sub('<p.*?</p>', '', b, flags=re.S)) else b)
        if path.name in {'index.html','method.html','changes.html'}:
            text = re.sub(r'<!-- timeline-summary -->.*?<!-- /timeline-summary -->', '', text, flags=re.S)
            text = text.replace('<main class="main">', '<main class="main"><!-- timeline-summary --><section class="note" id="timeline-summary"><p><strong>'+SUMMARY+'</strong></p><p>'+BUFFER+'</p><p>'+POLICY+'</p></section><!-- /timeline-summary -->', 1)
        text = re.sub(r'(Основная программа · |Core programme · |Редакция |Revision )4\.[34567]', lambda m:m[1]+VERSION, text)
        text = re.sub(r'(?:months/\d{4}-\d{2}\.html)#guide-([A-Za-z0-9]+)',
                      lambda m: f'months/{by_id[m[1]]["start"][:7]}.html#guide-{m[1]}' if m[1] in by_id else f'curriculum.html#{m[1]}', text)
        # These notices use list items or a warning div rather than paragraphs.
        text = replace_elements(text, lambda t, a: t == 'div' and 'warning' in a.get('class', '').split(),
                                lambda b, a: '<div class="warning">'+POLICY+'</div>' if re.search(r'85 h|85 ч|120 ч чтения|120 h of reading|31\.12\.2026|31 December 2026|18\.12\.2027|18 December 2027', b) or ('2028' in b and ('Старт ' in b or 'Start ' in b)) else b)
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
            learning = literature['learning_hours_total']
            text = re.sub(r'<strong>(?:525|645|701)</strong>', f'<strong>{learning}</strong>', text)
            text = re.sub(r'(?:525|645|701) ч изучения', f'{learning} ч изучения', text)
            text = re.sub(r'(?:525|645|701) learning hours', f'{learning} learning hours', text)
            for key in estimate['order']:
                if key not in literature.get('routes', {}):
                    continue
                item = by_id[key]
                hours_value = stage_learning_hours(item)
                row_pattern = r'<tr><td><a href="curriculum.html#' + re.escape(key) + r'">.*?</td><td>.*?</td>'
                replacement = f'<tr><td><a href="curriculum.html#{key}">{key}</a> · {hours_value} {bi("ч", "h")}</td><td><a href="months/{item["start"][:7]}.html#guide-{key}">{fmt(item["start"])}</a></td>'
                text, _ = re.subn(row_pattern, replacement, text, count=1, flags=re.S)
            def library_row(block, attrs):
                match = re.match(r'<tr><td><a href="curriculum.html#([A-Za-z0-9]+)">',block)
                if match and match[1] in literature['routes'] and '#ref-' in block:
                    return library_stage_row(match[1],by_id[match[1]],literature['routes'][match[1]],literature)
                return block
            text = replace_elements(text,lambda t,a: t == 'tr',library_row)
            text = re.sub(r'<!-- foundation-path -->.*?<!-- /foundation-path -->','',text,flags=re.S)
            text = re.sub(r'<!-- reference-additions -->.*?<!-- /reference-additions -->','',text,flags=re.S)
            learning_path = json.loads((ROOT / 'learning-path.json').read_text())
            text = text.replace('<section id="reading-policy">',foundation_path(learning_path,literature)+'<section id="reading-policy">',1)
            text = text.replace('<footer>',reference_additions(literature)+'<footer>',1)
            # Only the bibliographic count statistic, not original-source counts.
            text = re.sub(r'<strong>\d+</strong><span lang="ru">(?:проверенная запись каталога|записей каталога)</span><span lang="en">(?:reviewed catalog entries|catalog entries)</span>',
                          f'<strong>{len(literature["references"])}</strong>'+bi('записей каталога','catalog entries'),text)
            updated_refs = {f'ref-{r["id"]}':r for r in literature['references']
                            if r['id'] in {'math-feedback','math-modern-robotics','H-SLOCUM'}}
            text = replace_elements(text, lambda t,a: t == 'details' and a.get('id') in updated_refs,
                                    lambda _b,a: reference_card(updated_refs[a['id']]))
        # Refresh current claims by scope, never replace bare numbers in prices
        # or in the archived extended syllabus.
        def reviewed_paragraph(block, attrs):
            plain = html.unescape(re.sub('<[^>]+>', '', block))
            if ('120 ч' in plain and ('диагностик' in plain or 'зачёт' in plain)) or '120 h of reading' in plain:
                return '<p>'+POLICY+'</p>'
            if path.name == 'method.html' and any(s in plain for s in ['Аппаратная часть сокращена лишь', 'hardware scope is reduced by only']):
                return '<p>'+bi('Новые темы получили не меньше времени изучения, чем до прежнего сокращения. Электроника — 120 ч, CAD — 160 ч, MCU — 120 ч, приводной стенд — 104 ч. Время сокращено в знакомой программной работе, повторной обработке данных и оформлении уже выполненных проверок.', 'New topics retain at least their pre-compression learning time. Electronics: 120 h; CAD: 160 h; MCU: 120 h; actuator rig: 104 h. Savings come from familiar coding, shared analysis and reviewing existing evidence.')+'</p>'
            if 'optional tail PCB' in plain.lower() or 'Опциональная плата хвоста не входит' in plain:
                return '<p>'+bi(f'Опциональная плата хвоста не входит в 340 ч хвоста и {duration_text(core_minutes)} основной программы. Её 40–60 ч требуют отдельного пересчёта. Свободных часов до конца года нет.', f'The optional tail PCB is outside the tail’s 340 h and the {duration_text(core_minutes,"en")} core. Its 40–60 h require a separate reforecast. No unallocated hours remain before year-end.')+'</p>'
            if path.name == 'changes.html' and ('Сохранены все часы проектов' in plain or 'All arm425' in plain):
                return '<p>'+bi('Редакция 4.6: все 127 заданий пересмотрены под опыт учащегося. Новые темы получили 701 ч изучения вместо 525. Реализация — 1 235 ч, проверка — 664 ч. Три физических проекта и критерии приёмки сохранены; повторные отчёты и общая программная инфраструктура учтены один раз.', 'Revision 4.6: all 127 tasks were reviewed for the learner’s experience. Learning increases from 525 to 701 h; implementation is 1,235 h and verification 664 h. All three physical projects and acceptance criteria remain; shared software and repeated evidence reviews are counted once.')+'</p><p><a href="method.html#hour-review">'+bi('Проверка каждого задания →','Review every task →')+'</a></p>'
            if path.name in {'projects.html', 'method.html', 'growth.html', 'curriculum.html'}:
                block = re.sub(r'425(?= (?:ч|h|hours)\b)', '406', block)
                block = block.replace('arm’s 425 h', 'arm’s 406 h')
            return block
        text = replace_elements(text, lambda t, a: t == 'p', reviewed_paragraph)
        if path.name == 'projects.html':
            text = re.sub(r'425(?= (?:ч|h|hours)\b)', '406', text)
        # Stage headings used to retain historic hours even after task updates.
        if path.name == 'curriculum.html':
            def stage_section(block, attrs):
                item = by_id[attrs['id']]
                header = '<p class="small">'+bi(f'{amount(item["minutes"])} ч · {dates(item)}', f'{amount(item["minutes"])} h · {dates(item)}')+'</p>'
                return re.sub(r'<p class="small"><span lang="ru">[\d:]+ ч · .*?</p>', lambda m: header, block, count=1, flags=re.S)
            text = replace_elements(text, lambda t, a: t == 'section' and a.get('id') in by_id, stage_section)
        if path.name == 'index.html':
            text = text.replace('<strong>13</strong>', '<strong>12</strong>')
            def stage_summary_row(block, attrs):
                if 'data-task=' in block:
                    return block
                cells = re.findall(r'<td>(.*?)</td>', block, flags=re.S)
                if len(cells) == 3:
                    match = re.fullmatch(r'<a href="curriculum.html#([A-Za-z0-9]+)">.*?</a>', cells[0], flags=re.S)
                    if match and match[1] in by_id:
                        item = by_id[match[1]]
                        return '<tr><td>'+cells[0]+f'</td><td>{amount(item["minutes"])}</td><td>{dates(item)}</td></tr>'
                return block
            text = replace_elements(text, lambda t, a: t == 'tr', stage_summary_row)
            text = text.replace('<strong>2 600</strong>',f'<strong>{amount(core_minutes)}</strong>')
        if path.name == 'changes.html':
            def comparison(block, attrs):
                if 'Revision 3' not in block or 'Mathematics and control' not in block:
                    return block
                groups = [
                    ('Математика и управление','Mathematics and control',1200,['M02','M03','M08','D1','D2','M11','M10','M19']),
                    ('ПО, ROS и ИИ','Software, ROS and AI',920,['M01','S1','S2','M13','M16','M17','M14','M18','M24']),
                    ('Аппаратная база и три устройства','Hardware foundations and three devices',1655,['M04','M05','M06','M07','L1','M22','M23','A1','A2','A3','T1','T2','T3']),
                    ('Общая приёмка','Shared acceptance',80,['G1','G2','G3','G4']),
                ]
                rows=[]
                for ru,en,old,keys in groups:
                    now=sum(by_id[k]['minutes'] for k in keys)
                    rows.append('<tr><td>'+bi(ru,en)+f'</td><td>{old}</td><td>{amount(now)}</td><td>−{amount(old*60-now)}</td></tr>')
                for ru,en,old,now in [('Основные работы','Core work',3855,core_minutes),('Резерв','Allowance',300,0),('Всего','Total',4155,core_minutes)]:
                    rows.append('<tr><td>'+bi(ru,en)+f'</td><td>{old}</td><td>{amount(now)}</td><td>−{amount(old*60-now)}</td></tr>')
                return '<table><thead><tr><th>'+bi('Часть','Part')+'</th><th>'+bi('Редакция 3, ч','Revision 3, h')+'</th><th>'+bi(f'Основная программа {START.year}, ч:мин',f'{START.year} core, h:min')+'</th><th>'+bi('Изменение','Change')+'</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table>'
            text=replace_elements(text,lambda t,a:t=='table',comparison)
            text=text.replace('Полный вывод уравнений динамики двухзвенного механизма 2R','Полный вывод пространственной многозвенной динамики').replace('Complete 2R dynamics derivation','Full spatial multibody dynamics derivation')
            text=text.replace('SLAM/навигация, распределение сил через QP','SLAM/навигация, трёхмерное распределение сил через QP').replace('SLAM/navigation, force-QP/MPC/WBC','SLAM/navigation, 3D force-QP/MPC/WBC')
            def revision_note(block,attrs):
                if '701 ч изучения вместо 525' in block:
                    return '<p>'+bi('Редакция 4.8: ознакомление 2 января, учёба с понедельника 4 января, завершение 31 декабря 2027. Изучение — 701 ч, реализация — 1 231 ч, проверка — 659 ч 40 мин. Для сохранения 50 ч/неделю сняты 8 ч 20 мин знакомой программной и организационной работы; физические испытания сохранены.', 'Revision 4.8: orientation on 2 January, study from Monday 4 January, finish 31 December 2027. Learning: 701 h; implementation: 1,231 h; verification: 659 h 40 min. Retain 50 h/week by removing 8 h 20 min of familiar coding/organization; physical trials remain.')+'</p>'
                return block
            text=replace_elements(text,lambda t,a:t=='p',revision_note)
        if path.name == 'method.html':
            groups = [
                ('Математика, кинематика, управление и походка', 'Maths, kinematics, control and gait', ['M02','M03','M08','D1','D2','M11','M10','M19']),
                ('ПО, ROS, симуляция, зрение и ML', 'Software, ROS, simulation, vision and ML', ['M01','S1','S2','M13','M16','M17','M14','M18','M24']),
                ('Электроника, CAD, MCU и привод', 'Electronics, CAD, MCU and actuator', ['M04','M05','M06','M07']),
                ('Первая физическая нога', 'First physical leg', ['L1']),
                ('Четыре → шесть ног', 'Four → six legs', ['M22','M23']),
                ('Манипулятор', 'Robotic arm', ['A1','A2','A3']),
                ('Хвост', 'Tail', ['T1','T2','T3']),
                ('Приёмка по готовым доказательствам', 'Acceptance using existing evidence', ['G1','G2','G3','G4']),
            ]
            def method_summary(block, attrs):
                if not ('Math' in block and 'kinematics' in block):
                    return block
                rows = []
                for ru, en, ids in groups:
                    value = sum(by_id[k]['hours'] for k in ids)
                    refs = ', '.join(f'<a href="curriculum.html#{k}">{k}</a>' for k in ids)
                    rows.append('<tr><td>'+bi(ru,en)+f'</td><td>{amount(round(value*60))}</td><td>{refs}</td></tr>')
                rows += ['<tr><td>'+bi('Обязательная программа','Required programme')+f'</td><td>{amount(core_minutes)}</td><td>{fmt(by_id["G4"]["end"])}</td></tr>',
                         '<tr><td>'+bi('Свободная ёмкость','Unallocated capacity')+'</td><td>0</td><td>'+bi('Средняя рабочая оценка без отдельного процента на переделки','Nominal effort without a blanket rework percentage')+'</td></tr>',
                         '<tr><td>'+bi('Доступное время','Available capacity')+f'</td><td>{amount(capacity_minutes)}</td><td>'+bi(f'{workday_count} рабочих дней по 8 ч 20 мин',f'{workday_count} workdays at 8 h 20 min')+'</td></tr>']
                return '<table><thead><tr><th>'+bi('Часть','Part')+'</th><th>'+bi('Часы','Hours')+'</th><th>'+bi('Этапы','Stages')+'</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table>'
            text = replace_elements(text, lambda t, a: t == 'table', method_summary)
            text = re.sub(r'<!-- task-hour-review -->.*?<!-- /task-hour-review -->', '', text, flags=re.S)
            audit = ['<!-- task-hour-review --><section id="hour-review"><h2>'+bi('Все 127 заданий: индивидуальная оценка','All 127 tasks: individual estimates')+'</h2><p>'+POLICY+'</p>']
            for stage, item in by_id.items():
                rows = [r for r in review['tasks'] if r['stage'] == stage]
                if not rows:
                    continue
                audit.append('<details><summary>'+stage+' · '+bi(item['title'])+f' · {amount(item["minutes"])} '+bi('ч','h')+'</summary><div><p>'+bi(item['rationale'])+'</p><table><thead><tr><th>'+bi('Задание','Task')+'</th><th>'+bi('Изучение / реализация / проверка','Learn / build / verify')+'</th><th>'+bi('Всего','Total')+'</th></tr></thead><tbody>')
                for row in rows:
                    h = row['after']
                    audit.append('<tr><td>'+bi(row['title'])+f'<p class="small" lang="ru">{html.escape(row["reason"])}</p></td><td>{amount(round(h["learn"]*60))} / {amount(round(h["build"]*60))} / {amount(round(h["verify"]*60))}</td><td>{amount(round(row["hours"]*60))}</td></tr>')
                audit.append('</tbody></table></div></details>')
            audit.append('<p><a href="task-hour-review.md">'+bi('Полный отчёт с причинами изменений','Full review with change reasons')+'</a> · <a href="task-hour-review.json">JSON</a></p></section><!-- /task-hour-review -->')
            text = text.replace('<footer>', ''.join(audit)+'<footer>', 1)
        # Update current total claims with units; historic bare table values stay
        # in the extended archive rather than being replaced as arbitrary numbers.
        if path.name != 'full-syllabus.html':
            text = text.replace('2 600 ч',duration_text(core_minutes)).replace('2,600 h',duration_text(core_minutes,'en'))
            text = text.replace('2,600 work hours',duration_text(core_minutes,'en')+' of work')
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
        if key == CONFIG['orientation']['date'][:7]:
            parts.append('<section class="note" id="orientation"><h2>'+bi('2 января — ознакомление с планом','2 January — programme orientation')+'</h2><p>'+bi('Изучить структуру, материалы и порядок работы. Учебные задания и их часы начинаются в понедельник, 4 января; ознакомление в основной объём не засчитывается.', 'Review structure, materials and work order. Study tasks and their allocated hours start Monday 4 January; orientation is not counted in core effort.')+'</p></section>')
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
                parts.append(update_reading_block(guides[stage], stage, by_id, literature, '../'))
        parts.append('<div class="panel"><h3>'+bi('Закрытие месяца','Month-end check')+'</h3><p>'+bi('Записать фактические часы, результаты и PASS/HOLD. Если работа задерживается, пересчитать прогноз; непройденные проверки не засчитывать.', 'Record actual hours, outcomes and PASS/HOLD. If work is delayed, reforecast completion; do not mark unmet gates as passed.')+'</p></div><div class="month-nav">')
        for neighbor in [month_index-1,month_index+1]:
            if 0 <= neighbor < len(months):
                target = months[neighbor]['page'][7:]
                parts.append(f'<a href="{target}">{label(target[:7])}</a>')
        parts.append('</div><footer>'+bi(f'Календарь {VERSION} · 11.11.2026 · 50 ч/неделю.',f'Calendar {VERSION} · 11 November 2026 · 50 h/week.')+'</footer></main></div></body></html>')
        pages[ROOT/month['page']] = '\n'.join(parts)
    # Keep old month URLs usable, but remove obsolete monthly assignments.
    active_month_paths = {ROOT / month['page'] for month in months}
    for old_path in (ROOT / 'months').glob('*.html'):
        if old_path not in active_month_paths:
            pages[old_path] = prefix + '<h1>'+bi(f'Календарь перенесён на {START.year} год',f'Calendar moved to {START.year}')+'</h1><p>'+bi('2 января — ознакомление с планом; учебные задания с понедельника, 04.01.2027.','2 January is programme orientation; study tasks start Monday 4 January 2027.')+'</p><a href="2027-01.html">'+label('2027-01')+'</a></main></div></body></html>'
    for path, text in pages.items():
        path.write_text(text)
    procurement['baseline_hours_unchanged'] = hours(core_minutes)
    procurement['calendar_updated_on'] = '2026-11-11'
    write_json('procurement.json', procurement)
    print(f'Rendered {len(months)} months, {len(items)} stages; {by_id["G4"]["end"]} + {buffer_minutes} buffer minutes.')


if __name__ == '__main__':
    main()
