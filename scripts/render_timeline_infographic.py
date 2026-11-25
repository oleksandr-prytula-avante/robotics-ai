"""Accessible HTML timeline, derived only from the active schedule."""
import html
import re
from datetime import date, timedelta


def forecast_dates(schedule, weekly_hours, extra_percent, vacation):
    """Apply the scenarios documented in plan-forecast.md to cumulative effort."""
    day = date.fromisoformat(schedule['start'])
    excluded = {date.fromisoformat(value) for value in schedule['excluded_dates']}
    if vacation:
        # Two illustrative weeks starting on the second Monday in July 2027.
        july = date(day.year, 7, 1)
        monday = july + timedelta(days=(-july.weekday()) % 7 + 7)
        excluded.update(monday + timedelta(days=offset) for offset in range(14))
    available = required = 0
    dates = {}
    for item in schedule['items']:
        required += item['minutes'] * (100 + extra_percent)
        while available < required:
            while day.weekday() == 6 or day in excluded:
                day += timedelta(days=1)
            available += weekly_hours * 1000
            finish = day.isoformat()
            day += timedelta(days=1)
        dates[item['id']] = finish
    return dates


def render_controls(tracks, items, bi):
    out = ['<div class="roadmap-controls" data-roadmap-controls hidden>',
           '<div class="roadmap-filters" role="group" aria-labelledby="track-filter-label">',
           '<span id="track-filter-label" class="visually-hidden">' + bi('Фильтр направлений', 'Filter tracks') + '</span>']
    for key, ru, en in [('all', 'Все этапы', 'All stages'), *tracks]:
        out.append(f'<button type="button" class="roadmap-{key}" data-track-filter="{key}" '
                   f'aria-pressed="{str(key == "all").lower()}">{bi(ru, en)}</button>')
    out.append('</div>')
    for lang, label in [('ru', 'Перейти к этапу'), ('en', 'Jump to a stage')]:
        out.append(f'<label class="roadmap-picker" lang="{lang}">{label}'
                   f'<select data-stage-picker aria-controls="roadmap-stage-details">')
        for item in items:
            key = item['id']
            title = html.escape(item['title'][lang])
            out.append(f'<option value="{key}" data-track="{item["track"]}">{key} · {title}</option>')
        out.append('</select></label>')
    out.append('</div>')
    return ''.join(out)


def render_stage_details(items, bi, duration):
    out = ['<div class="roadmap-stage-details" id="roadmap-stage-details" aria-live="polite">']
    for item in items:
        key = item['id']
        out.append(f'<article data-stage-detail="{key}" class="roadmap-stage-card roadmap-{item["track"]}" hidden>'
                   f'<div class="roadmap-stage-heading"><div><span class="roadmap-stage-code">{key}</span>'
                   f'<h3>{bi(item["title"])}</h3></div><div class="roadmap-stage-total">'
                   f'{duration(item["minutes"])}</div></div>')
        dates = ' — '.join(date.fromisoformat(item[field]).strftime('%d.%m.%Y') for field in ('start', 'end'))
        out.append(f'<p class="roadmap-stage-date">{dates} · '
                   + bi('номинальный календарь', 'nominal calendar') + '</p>')
        if item['track'] != 'capacity':
            out.append('<div class="roadmap-effort"><dl>')
            for field, ru, en in [('learn', 'Изучение', 'Study'), ('build', 'Реализация', 'Build'),
                                  ('verify', 'Проверка', 'Verify')]:
                minutes = sum(round(task[field] * 60) for task in item['tasks'])
                out.append(f'<div><dt>{bi(ru, en)}</dt><dd>{duration(minutes)}</dd></div>')
            out.append('</dl></div>')
        out.append('<ol class="roadmap-tasks">')
        for task in item['tasks']:
            out.append(f'<li><span>{bi(task["title"])}</span><small>{duration(round(task["hours"] * 60))}</small></li>')
        out.append(f'</ol><a class="roadmap-detail-link" href="curriculum.html#{key}">'
                   + bi('Полная программа этапа →', 'Full stage syllabus →') + '</a></article>')
    return ''.join([*out, '</div>'])


def render_infographic(schedule, bi, duration):
    start = date.fromisoformat(schedule.get('orientation',{}).get('date',schedule['start']))
    deadline = date.fromisoformat(schedule['deadline'])
    days = (deadline - start).days + 1
    items = {item['id']: item for item in schedule['items']}
    tracks = [
        ('core', 'Инженерная база', 'Foundations'),
        ('hexapod', 'Гексапод', 'Hexapod'),
        ('arm', 'Манипулятор', 'Robotic arm'),
        ('tail', 'Хвост', 'Tail'),
        ('gate', 'Приёмки', 'Acceptance'),
        ('capacity', 'Запас', 'Buffer'),
    ]
    active_tracks = {item['track'] for item in items.values()}
    tracks = [track for track in tracks if track[0] in active_tracks]

    def position(day):
        return (day - start).days / days * 100

    def short_date(value):
        return date.fromisoformat(value).strftime('%d.%m.%Y')

    month_labels_ru = 'Янв Фев Мар Апр Май Июн Июл Авг Сен Окт Ноя Дек'.split()
    month_labels_en = 'Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split()
    month_cells, grid = [], []
    for month in schedule['months']:
        first = date(month['year'], month['month'], 1)
        next_month = (first.replace(day=28) + timedelta(days=4)).replace(day=1)
        left = position(max(first, start))
        width = (min(next_month, deadline + timedelta(days=1)) - max(first, start)).days / days * 100
        styles = f'left:{left:.5f}%;width:{width:.5f}%'
        year = f'<small>{first.year}</small>' if first == start or first.month == 1 else ''
        month_cells.append(f'<a class="roadmap-month" href="{month["page"]}" style="{styles}">{year}'
                           + bi(month_labels_ru[first.month-1], month_labels_en[first.month-1]) + '</a>')
        grid.append(f'<i class="roadmap-gridline" style="left:{left:.5f}%" aria-hidden="true"></i>')

    out = ['<!-- timeline-infographic -->', '<section class="roadmap" id="timeline" aria-labelledby="timeline-title">',
           '<div class="roadmap-heading"><div><h2 id="timeline-title">' + bi('От базы к трём роботам', 'From foundations to three robots')
           + '</h2></div><a class="roadmap-method" href="method.html">'
           + bi('Расчёт часов ↗', 'Hours & method ↗') + '</a></div>',
           '<div class="roadmap-stats">']
    for value, ru, en in [
        (short_date(schedule['start']), 'Старт учёбы', 'Study starts'),
        (short_date(schedule['work_finish']), 'Номинальный финиш', 'Nominal finish'),
    ]:
        out.append('<div><span class="roadmap-stat-label">' + bi(ru, en)
                   + '</span> <strong>' + value + '</strong></div>')
    out += ['</div>', render_controls(tracks, items.values(), bi),
            '<div class="roadmap-scroll" tabindex="0" role="region" aria-labelledby="timeline-title">',
            '<div class="roadmap-chart"><div class="roadmap-axis"><div>'
            + bi('Направление / часы', 'Track / hours') + '</div><div class="roadmap-months">'
            + ''.join(month_cells) + '</div></div>']
    for track, ru, en in tracks:
        members = [item for item in schedule['items'] if item['track'] == track]
        minutes = sum(round(item['hours'] * 60) for item in members)
        out.append(f'<div class="roadmap-row roadmap-{track}" data-roadmap-track="{track}"><div class="roadmap-label"><span>'
                   + bi(ru, en) + '</span><small>' + duration(minutes)
                   + '</small></div><div class="roadmap-lane">' + ''.join(grid))
        for item in members:
            first, last = item['segments'][0], item['segments'][-1]
            left = position(date.fromisoformat(first['date'])) + first['day_offset_minutes'] / schedule['daily_minutes'] / days * 100
            right = position(date.fromisoformat(last['date'])) + (last['day_offset_minutes'] + last['minutes']) / schedule['daily_minutes'] / days * 100
            width = right - left
            # Gate dates use completion; ordinary bars span their real calendar interval.
            if track == 'gate':
                left = right
            styles = f'left:{left:.5f}%;width:{width:.5f}%'
            classes = 'roadmap-bar' + (' roadmap-gate-marker' if track == 'gate' else '')
            visible = item['id'] if width >= 3.5 and track not in {'gate', 'capacity'} else ''
            for lang in ('ru', 'en'):
                title = (f'{item["id"]} · {item["title"][lang]} · '
                         f'{short_date(item["start"])} — {short_date(item["end"])}')
                out.append(f'<a lang="{lang}" class="{classes}" href="curriculum.html#{item["id"]}" '
                           f'style="{styles}" data-timeline-stage="{item["id"]}" '
                           f'title="{html.escape(title)}" aria-label="{html.escape(title)}">{visible}</a>')
        out.append('</div></div>')
    out += ['</div></div>', '<p class="roadmap-caption">'
            + bi('Номинальный календарь. Выберите полосу или этап, чтобы увидеть задания и часы.',
                 'Nominal calendar. Select a bar or stage to see tasks and hours.') + '</p>',
            '<p class="small"><a href="months/'+schedule['orientation']['date'][:7]+'.html#orientation">'
            + bi(short_date(schedule['orientation']['date'])+' — ознакомление с планом; учебные часы с понедельника.',
                 short_date(schedule['orientation']['date'])+' — programme orientation; study hours begin Monday.')+'</a></p>',
            render_stage_details(items.values(), bi, duration)]
    checkpoints = [
        ('G1', 'hexapod', 'Первая нога', 'First leg'),
        ('G2', 'hexapod', 'Четыре ноги', 'Four legs'),
        ('M23', 'hexapod', 'Гексапод', 'Hexapod'),
        ('G3', 'arm', 'Манипулятор + ИИ', 'Arm + AI'),
        ('T3', 'tail', 'Хвост', 'Tail'),
        ('G4', 'gate', 'Общая приёмка', 'Final acceptance'),
    ]
    scenarios = [
        ('Номинал · 50 ч/нед.', 'Nominal · 50 h/week', None),
        ('50 ч · +15%', '50 h · +15%', (50, 15, False)),
        ('50 ч · +20%', '50 h · +20%', (50, 20, False)),
        ('50 ч · +15% · отдых', '50 h · +15% · time off', (50, 15, True)),
        ('45 ч · +15% · отдых', '45 h · +15% · time off', (45, 15, True)),
        ('40 ч · +15% · отдых', '40 h · +15% · time off', (40, 15, True)),
    ]
    out.append('<div class="roadmap-forecast"><div class="roadmap-forecast-heading"><h3>'
               + bi('Когда будут готовы проекты', 'When the projects are ready')
               + '</h3><a href="plan-forecast.md">' + bi('Допущения прогноза ↗', 'Forecast assumptions ↗')
               + '</a></div><fieldset class="roadmap-scenarios"><legend>'
               + bi('Сравните сроки приёмок · отдых = две недели', 'Compare acceptance dates · time off = two weeks')
               + '</legend>')
    for index, (ru, en, _) in enumerate(scenarios):
        checked = ' checked' if index == 3 else ''
        out.append(f'<input class="visually-hidden" type="radio" name="roadmap-scenario" '
                   f'id="roadmap-scenario-{index}"{checked}><label for="roadmap-scenario-{index}">{bi(ru, en)}</label>')
    for index, (_, _, params) in enumerate(scenarios):
        dates = (forecast_dates(schedule, *params) if params else
                 {key: item['end'] for key, item in items.items()})
        out.append(f'<div class="roadmap-milestones" data-roadmap-scenario="{index}">')
        for key, track, ru, en in checkpoints:
            finish = dates[key]
            out.append(f'<a class="roadmap-checkpoint roadmap-{track}" href="curriculum.html#{key}">'
                       f'<span class="roadmap-step">{key}</span><span><time datetime="{finish}">'
                       + short_date(finish) + '</time><strong>' + bi(ru, en) + '</strong></span></a>')
        out.append('</div>')
    out += ['</fieldset></div><div class="roadmap-footer"><span>'
            + bi('50 ч/нед · Пн–Сб · 8 ч 20 мин/день', '50 h/week · Mon–Sat · 8 h 20 min/day')
            + '</span><span>' + bi(f'Воскресенье — выходной; {deadline:%d.%m.%y} — рабочий день',
                                  f'Sunday off; {deadline:%d.%m.%y} is a workday')
            + '</span></div></section><!-- /timeline-infographic -->']
    return '\n'.join(out)


def update_homepage(source, schedule, bi, duration, policy):
    """Refresh the chart after the hero without accumulating generated blocks."""
    source = re.sub(r'<!-- timeline-infographic -->.*?<!-- /timeline-infographic -->', '', source, flags=re.S)
    source = re.sub(r'<!-- timeline-summary -->.*?<!-- /timeline-summary -->', '', source, flags=re.S)
    # The old homepage repeated the same calendar assumptions in three places.
    source = source.replace('<div class="note">' + policy + '</div>', '')
    source = source.replace('<p>' + policy + '</p>', '')
    chart = render_infographic(schedule, bi, duration)
    assumptions = ('<!-- timeline-summary --><details class="roadmap-assumptions" id="timeline-summary"><summary>'
                   + bi('Условия календаря и запас времени', 'Calendar assumptions and buffer')
                   + '</summary><div><p>' + policy + '</p></div></details><!-- /timeline-summary -->')
    return re.sub(r'(<section class="hero">.*?</section>)',
                  lambda match: match[0] + chart + assumptions, source, count=1, flags=re.S)
