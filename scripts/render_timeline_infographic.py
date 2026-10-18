"""Accessible HTML timeline, derived only from the active schedule."""
import html
import re
from datetime import date, timedelta


def render_infographic(schedule, bi, duration):
    start = date.fromisoformat(schedule['start'])
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
           '<div class="roadmap-heading"><div><div class="eyebrow">'
           + bi('Маршрут · 2026—2027', 'The route · 2026–2027')
           + '</div><h2 id="timeline-title">' + bi('От базы к трём роботам', 'From foundations to three robots')
           + '</h2></div><a class="roadmap-method" href="method.html">'
           + bi('Расчёт часов ↗', 'Hours & method ↗') + '</a></div>',
           '<div class="roadmap-stats">']
    for value, ru, en in [
        (short_date(schedule['start']), 'Старт', 'Start'),
        (short_date(schedule['work_finish']), 'Плановый финиш', 'Planned finish'),
        (duration(schedule['buffer_minutes']), 'Запас до конца года', 'Buffer through year-end'),
    ]:
        out.append('<div><span class="roadmap-stat-label">' + bi(ru, en)
                   + '</span><strong>' + value + '</strong></div>')
    out += ['</div><div class="roadmap-scroll" tabindex="0" role="region" aria-labelledby="timeline-title">',
            '<div class="roadmap-chart"><div class="roadmap-axis"><div>'
            + bi('Направление / часы', 'Track / hours') + '</div><div class="roadmap-months">'
            + ''.join(month_cells) + '</div></div>']
    for track, ru, en in tracks:
        members = [item for item in schedule['items'] if item['track'] == track]
        minutes = sum(round(item['hours'] * 60) for item in members)
        out.append(f'<div class="roadmap-row roadmap-{track}"><div class="roadmap-label"><span>'
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
            + bi('Полосы — календарные интервалы. Нажмите на этап, чтобы открыть задания.',
                 'Bars show calendar spans. Select a stage to open its tasks.') + '</p>',
            '<div class="roadmap-milestones">']
    checkpoints = [
        ('G1', 'hexapod', 'Первая нога', 'First leg'),
        ('G2', 'hexapod', 'Четыре ноги', 'Four legs'),
        ('M23', 'hexapod', 'Гексапод', 'Hexapod'),
        ('G3', 'arm', 'Манипулятор + ИИ', 'Arm + AI'),
        ('T3', 'tail', 'Хвост', 'Tail'),
        ('G4', 'gate', 'Общая приёмка', 'Final acceptance'),
    ]
    for index, (key, track, ru, en) in enumerate(checkpoints, 1):
        item = items[key]
        out.append(f'<a class="roadmap-checkpoint roadmap-{track}" href="curriculum.html#{key}">'
                   f'<span class="roadmap-step">{index:02}</span><span><time datetime="{item["end"]}">'
                   + short_date(item['end']) + '</time><strong>' + bi(ru, en) + '</strong></span></a>')
    out += ['</div><div class="roadmap-footer"><span>'
            + bi('50 ч/нед · Пн–Сб · 8 ч 20 мин/день', '50 h/week · Mon–Sat · 8 h 20 min/day')
            + '</span><span>' + bi('Выходные: 31.12.26 · 01.01.27 · 31.12.27',
                                  'Days off: 31.12.26 · 01.01.27 · 31.12.27')
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
