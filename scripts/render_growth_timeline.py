"""Build the optional-track forecast without changing the core calendar.

Run: python3 scripts/render_growth_timeline.py [--check]
Hours come only from development-map.json; this is a sequential all-tracks scenario.
"""
import argparse
import html
import json
import re
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = r'<!-- growth-timeline -->.*?<!-- /growth-timeline -->'
MONTHS_RU = 'Янв Фев Мар Апр Май Июн Июл Авг Сен Окт Ноя Дек'.split()
MONTHS_EN = 'Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split()


def bi(ru, en=None):
    if isinstance(ru, dict):
        ru, en = ru['ru'], ru['en']
    return f'<span lang="ru">{html.escape(ru)}</span><span lang="en">{html.escape(en)}</span>'


def read(name):
    return json.loads((ROOT / name).read_text())


def hours_range(track):
    if 'approximate_extra_hours_range' in track:
        value = track['approximate_extra_hours_range']
        low, high = value['low'], value['high']
    elif 'approx_extra_hours_range' in track:
        low, high = track['approx_extra_hours_range']
    else:
        low = high = track['hours']
    if not (0 < low <= high) or any(int(v * 60) != v * 60 for v in (low, high)):
        raise ValueError(f'Invalid hour range: {track["id"]}')
    return low, high


def next_monday(day):
    day += timedelta(days=1)
    while day.weekday() != 0:
        day += timedelta(days=1)
    return day


def allocate(tracks, start, daily_minutes, workdays, excluded_dates=()):
    """Allocate integer minutes, sharing the last day between consecutive tracks."""
    if daily_minutes <= 0 or not workdays or not set(workdays) <= set(range(7)):
        raise ValueError('Invalid work calendar')
    day, offset = start, 0
    excluded = set(excluded_dates)
    result, segments = [], []
    for track in tracks:
        remaining = track['minutes']
        if not isinstance(remaining, int) or remaining <= 0:
            raise ValueError('Track minutes must be positive integers')
        parts = []
        while remaining:
            while day.weekday() not in workdays or day.isoformat() in excluded:
                day += timedelta(days=1)
                offset = 0
            amount = min(remaining, daily_minutes - offset)
            part = dict(track=track['id'], date=day.isoformat(),
                        day_offset_minutes=offset, minutes=amount)
            parts.append(part)
            remaining -= amount
            offset += amount
            if offset == daily_minutes:
                day += timedelta(days=1)
                offset = 0
        result.append(dict(track, start=parts[0]['date'], end=parts[-1]['date']))
        segments.extend(parts)
    return dict(tracks=result, segments=segments,
                total_minutes=sum(t['minutes'] for t in result),
                start=result[0]['start'], end=result[-1]['end'])


def build_model(development, config, core):
    source = {t['id']: t for t in development['tracks']}
    order = [key for group in config['groups'] for key in group['tracks']]
    if Counter(order) != Counter(source.keys()):
        raise ValueError('Each development track must occur exactly once')
    done = set()
    for key in order:
        dependencies = set(source[key].get('prerequisites', [])) & source.keys()
        if not dependencies <= done:
            raise ValueError(f'Unmet track dependency: {key}: {dependencies - done}')
        done.add(key)
    if config['start_policy'] != 'next_monday_after_core':
        raise ValueError('Unknown start policy')
    start = next_monday(date.fromisoformat(core['calendar_finish']))
    model = dict(start=start.isoformat(), core_finish=core['calendar_finish'],
                 daily_minutes=config['daily_minutes'], workdays=config['workdays'],
                 excluded_dates=config['excluded_dates'], groups=config['groups'],
                 scenarios={})
    for scenario, index in [('low', 0), ('high', 1)]:
        tracks = [dict(id=key, title=source[key]['title'],
                       hours_range=list(hours_range(source[key])),
                       dependencies=[d for d in source[key].get('prerequisites', []) if d in source],
                       minutes=int(hours_range(source[key])[index] * 60)) for key in order]
        model['scenarios'][scenario] = allocate(tracks, start, config['daily_minutes'],
                                                config['workdays'], config['excluded_dates'])
    return model


def fmt(value):
    return date.fromisoformat(value).strftime('%d.%m.%Y')


def number(value):
    return f'{value:,}'.replace(',', ' ')


def render(model):
    low, high = (model['scenarios'][key] for key in ('low', 'high'))
    origin = date.fromisoformat(model['start'])
    last = date.fromisoformat(high['end'])
    chart_end = (last.replace(day=28) + timedelta(days=4)).replace(day=1)
    days = (chart_end - origin).days
    months = []
    month = origin.replace(day=1)
    while month < chart_end:
        following = (month.replace(day=28) + timedelta(days=4)).replace(day=1)
        left = max(month, origin)
        months.append((month, (left-origin).days/days*100, (following-left).days/days*100))
        month = following
    out = ['<!-- growth-timeline --><section class="roadmap growth-timeline" id="growth-timeline">',
           '<div class="roadmap-heading"><div><span class="eyebrow">'+bi('Дополнительные направления · 2028', 'Optional tracks · 2028')+'</span><h2>'+bi('Таймлайн после основной программы', 'Timeline after the core programme')+'</h2></div></div>',
           '<p class="small">'+bi('Сценарий прохождения всех 22 направлений по очереди. ACT — после инфраструктуры и симуляции. Можно выбрать отдельные ветки; этот сценарий не делает их обязательными.', 'A scenario covering all 22 tracks sequentially. ACT follows infrastructure and simulation. Individual branches remain optional; this scenario does not make them required.')+'</p>',
           '<div class="roadmap-stats"><div><span class="roadmap-stat-label">'+bi('Всего дополнительно', 'Total additional work')+'</span><strong>'+number(low['total_minutes']//60)+'–'+number(high['total_minutes']//60)+' '+bi('ч','h')+'</strong></div>',
           '<div><span class="roadmap-stat-label">'+bi('Старт после основной программы', 'Start after the core programme')+'</span><strong>'+fmt(model['start'])+'</strong></div>',
           '<div><span class="roadmap-stat-label">'+bi('Окончание по двум оценкам', 'Finish under the two estimates')+'</span><strong>'+fmt(low['end'])+' — '+fmt(high['end'])+'</strong></div></div>',
           '<fieldset class="growth-estimates"><legend>'+bi('Выберите оценку трудоёмкости', 'Choose an effort estimate')+'</legend>',
           '<input class="visually-hidden growth-estimate" type="radio" name="growth-estimate" id="growth-estimate-low"><label for="growth-estimate-low">'+bi('Нижняя · '+number(low['total_minutes']//60)+' ч', 'Lower · '+f'{low["total_minutes"]//60:,}'+' h')+'</label>',
           '<input class="visually-hidden growth-estimate" type="radio" name="growth-estimate" id="growth-estimate-high" checked><label for="growth-estimate-high">'+bi('Верхняя · '+number(high['total_minutes']//60)+' ч', 'Upper · '+f'{high["total_minutes"]//60:,}'+' h')+'</label><div class="growth-scenarios">']
    for scenario in ('low', 'high'):
        plan = model['scenarios'][scenario]
        tracks = {t['id']: t for t in plan['tracks']}
        label = bi('Нижняя оценка', 'Lower estimate') if scenario == 'low' else bi('Верхняя оценка', 'Upper estimate')
        out += [f'<div class="growth-scenario growth-scenario-{scenario}" data-growth-scenario="{scenario}">',
                '<p class="growth-forecast"><strong>'+label+'</strong> · '+fmt(plan['start'])+' — '+fmt(plan['end'])+' · '+bi('50 ч/неделю', '50 h/week')+'</p>',
                f'<p class="visually-hidden" id="growth-chart-label-{scenario}">'+bi('Таймлайн дополнительных направлений', 'Optional tracks timeline')+'</p>',
                f'<div class="roadmap-scroll" tabindex="0" role="region" aria-labelledby="growth-chart-label-{scenario}"><div class="roadmap-chart">',
                '<div class="roadmap-axis"><div>'+bi('Направление', 'Track')+'</div><div class="roadmap-months">']
        for month, left, width in months:
            out.append(f'<div class="roadmap-month" style="left:{left:.5f}%;width:{width:.5f}%"><small>{month.year}</small>'+bi(MONTHS_RU[month.month-1], MONTHS_EN[month.month-1])+'</div>')
        out.append('</div></div>')
        for group in model['groups']:
            group_hours = sum(tracks[key]['minutes'] for key in group['tracks']) // 60
            out.append(f'<div class="roadmap-row growth-{group["id"]}"><div class="roadmap-label">'+bi(group['title'])+'<small>'+str(group_hours)+' '+bi('ч','h')+'</small></div><div class="roadmap-lane">')
            for _, left, _ in months:
                out.append(f'<i class="roadmap-gridline" style="left:{left:.5f}%"></i>')
            # Use actual minute positions so tracks sharing one date do not overlap.
            for key in group['tracks']:
                track = tracks[key]
                parts = [p for p in plan['segments'] if p['track'] == key]
                start_day, end_day = (date.fromisoformat(track[field]) for field in ('start','end'))
                begin = (start_day-origin).days + parts[0]['day_offset_minutes']/model['daily_minutes']
                end = (end_day-origin).days + (parts[-1]['day_offset_minutes']+parts[-1]['minutes'])/model['daily_minutes']
                visible = 'ACT' if key == 'D_IL' else key.replace('G-', '').replace('D_', '').replace('D-H', '')
                if len(visible)>9 or (end-begin)/days*100<4:
                    visible = ''
                for lang in ('ru','en'):
                    title=f'{key} · {track["title"][lang]} · {fmt(track["start"])} — {fmt(track["end"])}'
                    out.append(f'<a lang="{lang}" class="roadmap-bar" href="#{key}" style="left:{begin/days*100:.5f}%;width:{(end-begin)/days*100:.5f}%" data-growth-track="{key}" title="{html.escape(title)}" aria-label="{html.escape(title)}">{visible}</a>')
            out.append('</div></div>')
        out += ['</div></div><p class="roadmap-caption">'+bi('Одинаковая шкала для обеих оценок. Нажмите на полосу или название в таблице, чтобы открыть задания. На узком экране график прокручивается по горизонтали.', 'Both estimates use the same scale. Select a bar or table title to open the tasks. The chart scrolls horizontally on narrow screens.')+'</p>',
                '<div class="table-wrap"><table class="growth-schedule"><caption>'+label+' · '+bi('точные даты этапов', 'stage dates')+'</caption><thead><tr><th>'+bi('Этап и результат', 'Stage and outcome')+'</th><th>'+bi('Часы', 'Hours')+'</th><th>'+bi('Период', 'Dates')+'</th></tr></thead><tbody>']
        for group in model['groups']:
            out.append('<tr class="growth-group"><th colspan="3">'+bi(group['title'])+'</th></tr>')
            for key in group['tracks']:
                track=tracks[key]
                deps = ('<small>'+bi('После: ', 'After: ')+', '.join(f'<a href="#{d}">{d}</a>' for d in track['dependencies'])+'</small>') if track['dependencies'] else ''
                out.append(f'<tr data-growth-stage="{key}"><td><a href="#{key}"><span class="growth-code">{key}</span>'+bi(track['title'])+'</a>'+deps+'</td><td class="num">'+str(track['minutes']//60)+'</td><td class="growth-dates">'+fmt(track['start'])+'<br>'+fmt(track['end'])+'</td></tr>')
        out.append('</tbody></table></div></div>')
    out += ['</div></fieldset><div class="note"><p>'+bi('Условия: Пн–Сб по 8 ч 20 мин; воскресенье свободно. Работа идёт последовательно, без двойного учёта часов. Направления могут делить один день. QP предшествует MPC, SLAM — навигации. Предполагается завершение всех проверок основной программы.', 'Assumptions: Mon–Sat, 8 h 20 min/day; Sundays off. Work is sequential, with no double-counted hours. Tracks may share one day. QP precedes MPC; SLAM precedes navigation. All core programme gates are assumed complete.')+'</p><p>'+bi('Это прогноз активной работы по одному ограниченному примеру на направление. Нижняя и верхняя оценки не являются вероятностями. Праздники, отпуск, доставка, ожидание вычислений и физическое продолжение ACT отдельно не заложены; при выборе реального проекта нужен пересчёт.', 'This forecasts active work on one bounded example per track. Lower and upper estimates are not probabilities. Holidays, vacation, delivery, compute waits and the ACT physical extension are not separately allocated; reforecast for the chosen real project.')+'</p></div></section><!-- /growth-timeline -->']
    return '\n'.join(out)


def outputs():
    model = build_model(read('development-map.json'), read('growth-timeline-config.json'), read('schedule.json'))
    page = (ROOT/'growth.html').read_text()
    block = render(model)
    if re.search(MARKER, page, flags=re.S):
        page = re.sub(MARKER, lambda _: block, page, count=1, flags=re.S)
    else:
        anchor = '<h2><span lang="ru">Как выбрать следующий шаг</span>'
        if page.count(anchor) != 1:
            raise ValueError('Missing growth timeline insertion anchor')
        page = page.replace(anchor, block + anchor, 1)
    return {'growth-timeline.json': json.dumps(model, ensure_ascii=False, indent=2)+'\n', 'growth.html': page}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args=parser.parse_args()
    for name, content in outputs().items():
        if args.check:
            if not (ROOT/name).exists() or (ROOT/name).read_text() != content:
                raise SystemExit(f'Stale growth timeline: {name}')
        else:
            (ROOT/name).write_text(content)
    print('Growth timeline is current.' if args.check else 'Rendered both optional-track timeline estimates.')


if __name__=='__main__':
    main()
