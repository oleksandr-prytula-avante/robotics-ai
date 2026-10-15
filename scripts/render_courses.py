"""Render the curated Udemy catalogue and its links. Run: python3 scripts/render_courses.py."""
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / 'courses.json').read_text())
COURSES = {c['id']: c for c in DATA['courses']}

def esc(value):
    return html.escape(str(value), quote=True)

def bi(ru, en=None):
    if isinstance(ru, dict):
        ru, en = ru['ru'], ru['en']
    return f'<span lang="ru">{esc(ru)}</span><span lang="en">{esc(en)}</span>'

def link(cid, detail=False):
    c = COURSES[cid]
    return f'<a href="{esc("#course-" + cid if detail else c["url"])}">{esc(c["title"])}</a>'

STATUS = {
    'strong': ('Хорошее совпадение', 'Strong match'),
    'partial': ('Частичное покрытие', 'Partial coverage'),
    'gap': ('Прямого курса не найдено', 'No direct match found'),
    'no_purchase': ('Без новой покупки', 'No new purchase'),
}

def route_table(routes, group, back):
    rows = []
    for rid, route in routes.items():
        refs = '<br>'.join(link(c, True) for c in route['courses']) or bi('Новая покупка не нужна', 'No new purchase')
        return_link = f'<a href="{back}#{rid}">{esc(rid)}</a>' if group != 'legacy' else esc(rid)
        rows.append(f'<tr id="route-{rid}"><td><b>{return_link}</b><br>{bi(route["title"])}</td><td>{refs}</td><td><span class="tag">{bi(*STATUS[route["status"]])}</span><p>{bi(route["note"])}</p></td></tr>')
    return '<div class="table-wrap"><table><thead><tr><th>'+bi('Секция', 'Section')+'</th><th>'+bi('Курс → карточка и покупка', 'Course → details and purchase')+'</th><th>'+bi('Как использовать', 'How to use')+'</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table></div>'

source = (ROOT / 'library.html').read_text()
prefix = source.split('<main class="main">')[0] + '<main class="main">'
prefix = prefix.replace('Литература и исходники · Robotics &amp; AI', 'Курсы Udemy · Robotics &amp; AI').replace('Reading and originals · Robotics &amp; AI', 'Udemy courses · Robotics &amp; AI').replace('class="active" href="library.html"', 'class="" href="library.html"')
parts = [prefix]
parts.append('<div class="hero"><span class="eyebrow">UDEMY · 15.10.2026</span><h1>'+bi('Видеокурсы к каждой секции', 'Video courses for every section')+'</h1><p class="lead">'+bi('23 курса с проверенной отдельной покупкой. Маршрут для 39 секций основной программы, исходных M01–M24 и 22 направлений развития.', '23 courses with verified individual-purchase offers. Routes for 39 core sections, original M01–M24 and 22 development tracks.')+'</p></div>')
parts.append('<div class="note"><p>'+bi('Проверены страницы Udemy, содержание, требования, даты обновления и возможность отдельной покупки. Платные уроки не просмотрены: это подборка по открытой программе, а не рецензия на полный курс. Все выбранные курсы на английском; наличие и качество русских субтитров не подтверждены.', 'Udemy pages, syllabi, requirements, update dates and individual-purchase offers were checked. Paid lessons were not watched: this is a public-syllabus selection, not a review of complete courses. All selected courses are in English; Russian subtitle availability and quality are unverified.')+'</p><p>'+bi('Цены — снимок предложения в USD от 15.10.2026, зависят от аккаунта, региона и акции. Итог проверять на Udemy. Курсы покупать по мере прохождения: повторное упоминание означает ту же покупку.', 'Prices are USD offer snapshots from 15 October 2026 and depend on account, region and promotion. Check the final price on Udemy. Buy as you progress: repeated mentions refer to the same purchase.')+'</p></div>')
parts.append('<section class="module" id="start"><h2>'+bi('С чего начать', 'Where to start')+'</h2><ol>')
for cid in DATA['starter']:
    c = COURSES[cid]
    parts.append(f'<li>{link(cid, True)} · ${c["price_usd_snapshot"]:.2f}</li>')
starter_total = sum(round(COURSES[cid]['price_usd_snapshot'] * 100) for cid in DATA['starter']) / 100
parts.append('</ol><p>'+bi(f'Эти три курса стоили ${starter_total:.2f} на момент проверки. C++ брать, если диагностика M01 выявила пробелы; ROS и математику проходить параллельно с заданиями. Следующая очередь: электроника → Fusion → ESP-IDF.', f'These three courses totalled ${starter_total:.2f} at verification. Buy C++ if the M01 diagnostic finds gaps; study ROS and mathematics alongside the tasks. Next: electronics → Fusion → ESP-IDF.')+'</p><p>'+bi('Видео заменяет часть изучения внутри секции. Полную длительность всех курсов нельзя добавлять к плану как обязательную: часы практики и проверки сохраняются, дополнительное обучение требует пересчёта.', 'Video replaces part of a section’s study time. Full course durations are not mandatory additions to the plan: retain build and verification time, and reforecast any extra study.')+'</p></section>')
parts.append('<p class="course-jumps">'+ ' · '.join(f'<a href="#{id}">{bi(ru,en)}</a>' for id,ru,en in [('core','Все секции','All sections'),('catalog','23 курса','23 courses'),('legacy','Исходные модули','Original modules'),('growth','Развитие','Development')])+'</p>')
parts.append('<section id="core"><h2>'+bi('Основная программа: секция → курс', 'Core programme: section → course')+'</h2>'+route_table(DATA['core_routes'],'core','curriculum.html')+'</section>')
parts.append('<section id="catalog"><h2>'+bi('Карточки курсов и прямые ссылки', 'Course details and direct links')+'</h2>')
for c in DATA['courses']:
    uses = [rid for rid,r in DATA['core_routes'].items() if c['id'] in r['courses']]
    badge = {'selected':('Выборочно по программе','Selected course sections'),'optional':('Необязательное дополнение','Optional supplement'),'alternative':('Альтернативное оборудование','Alternative hardware')}[c['tier']]
    parts.append(f'<article class="module anchor" id="course-{c["id"]}"><span class="tag">{bi(*badge)}</span><h3>{esc(c["title"])}</h3><p>{esc(c["instructor"])} · English · {esc(c["duration"])}</p><p class="small">'+bi(f'Обновлён: {c["updated"]} · {c["rating"]}/5 · {c["ratings"]:,} оценок', f'Updated: {c["updated"]} · {c["rating"]}/5 · {c["ratings"]:,} ratings')+'</p><p><b>'+bi('Что смотреть: ', 'Watch: ')+'</b>'+bi(c['watch'])+'</p><p><b>'+bi('Ограничения: ', 'Limitations: ')+'</b>'+bi(c['limitations'])+'</p>')
    if uses:
        parts.append('<p>'+bi('Секции: ', 'Sections: ')+', '.join(f'<a href="#route-{rid}">{rid}</a>' for rid in uses)+'</p>')
    parts.append(f'<a class="button secondary" href="{esc(c["url"])}">'+bi('Открыть курс на Udemy', 'Open course on Udemy')+'</a><p class="small">'+bi(f'Отдельная покупка доступна при проверке · ${c["price_usd_snapshot"]:.2f} · 15.10.2026', f'Individual purchase available when checked · ${c["price_usd_snapshot"]:.2f} · 15 Oct 2026')+'</p></article>')
parts.append('</section><section id="legacy"><h2>'+bi('Исходные M01–M24: перенесённые и отложенные темы', 'Original M01–M24: moved and deferred topics')+'</h2><p>'+bi('Остальные M-модули представлены в основной таблице. Здесь пять исходных модулей, которые перенесены или вынесены из ядра программы.', 'The other M modules appear in the core table. These five original modules were moved or deferred outside the core.')+'</p>'+route_table(DATA['legacy_routes'],'legacy','full-syllabus.html')+'</section>')
parts.append('<section id="growth"><h2>'+bi('Направления развития', 'Development tracks')+'</h2><p>'+bi('Не входят в обязательные покупки и часы основной программы. Пустая строка курсов означает, что надёжное прямое соответствие не выбрано.', 'Outside mandatory purchases and core programme hours. An empty course selection means no reliable direct match was selected.')+'</p>'+route_table(DATA['growth_routes'],'growth','growth.html')+'</section>')
parts.append('<footer>'+bi('Проверка: 15.10.2026 · Подборка дополняет программу 4.3.', 'Verified: 15 October 2026 · This selection supplements programme 4.3.')+' <a href="courses.json">'+bi('Данные подборки', 'Selection data')+'</a></footer></main></div></body></html>')
(ROOT / 'courses.html').write_text('\n'.join(parts)+'\n')

# Idempotent navigation links on active pages; archived originals stay intact.
for path in list(ROOT.glob('*.html')) + list((ROOT / 'months').glob('*.html')):
    text = path.read_text()
    text = re.sub(r'<a\b[^>]*data-course-nav[^>]*>.*?</a>', '', text, flags=re.S)
    relative = '../' if path.parent.name == 'months' else ''
    active = 'active' if path.name == 'courses.html' else ''
    nav = f'<a class="{active}" data-course-nav href="{relative}courses.html">'+bi('Курсы Udemy', 'Udemy courses')+'</a>'
    text, n = re.subn(r'(<a\b[^>]*href="(?:\.\./)?library.html"[^>]*>.*?</a>)', lambda m:m[0]+nav, text, count=1, flags=re.S)
    if n:
        path.write_text(text)

# Put a concise selection directly beside each core section and growth track.
for filename, key in [('curriculum.html','core_routes'),('growth.html','growth_routes')]:
    path = ROOT / filename
    text = re.sub(r'<!-- udemy-route:.*?<!-- /udemy-route -->','',path.read_text(), flags=re.S)
    for rid, route in DATA[key].items():
        refs = ' · '.join(link(cid) for cid in route['courses']) or bi('Новая покупка не нужна.', 'No new purchase needed.')
        block = f'<!-- udemy-route:{rid} --><div class="note course-route"><b>Udemy</b><p>{refs}</p><p>{bi(route["note"])}</p><a href="courses.html#route-{rid}">'+bi('Что смотреть, цены и ограничения →', 'What to watch, prices and limitations →')+'</a></div><!-- /udemy-route -->'
        if filename == 'growth.html':
            pattern = rf'(<details\b[^>]*\bid="{re.escape(rid)}"[^>]*>.*?</summary><div>)'
        else:
            pattern = rf'(<section\b[^>]*\bid="{re.escape(rid)}"[^>]*>.*?</h2>)'
        text, n = re.subn(pattern,lambda m:m[0]+block,text,count=1,flags=re.S)
        if n != 1:
            raise ValueError(f'Missing section {filename}:{rid}')
    path.write_text(text)
print(f'Rendered {len(COURSES)} courses and all route links')
