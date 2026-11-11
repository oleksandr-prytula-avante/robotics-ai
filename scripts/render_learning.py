"""Render task-linked reading and a connected foundation path from JSON."""
import html
from datetime import date


def bi(value, en=None):
    if isinstance(value, dict):
        value, en = value['ru'], value['en']
    return f'<span lang="ru">{html.escape(value)}</span><span lang="en">{html.escape(en)}</span>'


def source_link(ref, prefix=''):
    return f'<a href="{prefix}library.html#ref-{ref["id"]}">{bi(ref["title"])}</a>'


def reference_card(ref):
    out = [f'<details class="anchor" id="ref-{ref["id"]}"><summary>'+bi(ref['title'])+'</summary><div>',
           '<p class="small">'+html.escape(ref['authors'])+'</p>',
           '<p class="small">'+bi(ref['edition'])+'</p>',
           '<p><a href="'+html.escape(ref['url'],quote=True)+'">'+bi('Открыть первичный источник','Open primary source')+'</a></p>',
           '<p>'+bi(ref['access'])+'</p><p>'+bi(ref['selection'])+'</p>']
    if ref.get('limitations'):
        out.append('<p class="small">'+bi(ref['limitations'])+'</p>')
    if ref.get('status'):
        out.append('<p class="small">'+bi(ref['status'])+'</p>')
    for link in ref.get('links',[]):
        out.append('<p class="small"><a href="'+html.escape(link['url'],quote=True)+'">'+html.escape(link.get('title',link['url']))+'</a></p>')
    return ''.join(out)+'</div></details>'


def reading_route(stage, item, literature, prefix=''):
    route = literature['routes'][stage]
    refs = {r['id']: r for r in literature['references']}
    out = [f'<div class="reading-route" data-reading-stage="{stage}"><h3>'+bi('Что читать сейчас','What to read now')+'</h3>',
           '<p class="small">'+bi(f'Изучение на весь этап: {route["learn_hours"]} ч, включая чтение, разбор примеров и самостоятельное объяснение. Блоки ниже распределяют эти часы; они не добавляются к календарю.',
                                    f'Learning for the complete stage: {route["learn_hours"]} h, including reading, worked examples and independent explanation. The units below allocate these hours; they add no calendar time.')+'</p>']
    if route.get('note'):
        out.append('<p>'+bi(route['note'])+'</p>')
    out.append('<ul>')
    for reading in route['readings']:
        ref = refs[reading['ref']]
        out.append(f'<li data-reading-ref="{ref["id"]}"><a href="{html.escape(reading.get("url",ref["url"]),quote=True)}">'+bi(ref['title'])+'</a><p>'+bi(reading['selection'])+'</p>')
        links = {link['url']: link.get('title','') for link in ref.get('links',[]) if link.get('title')}
        links.update({link['url']:link.get('title','') for link in reading.get('links',[]) if link.get('title')})
        for url,title in links.items():
            out.append(f'<p class="small"><a href="{html.escape(url,quote=True)}">{html.escape(title)}</a></p>')
        out.append('<p class="small">'+bi(ref['access'])+'</p></li>')
    out.append('</ul><details><summary>'+bi('Часы и проверка понимания по заданиям','Task hours and understanding checks')+'</summary><div>')
    for unit in route.get('study_units',[]):
        index = int(unit['task'].rsplit('.',1)[1])-1
        task = item['tasks'][index]
        out += [f'<div class="panel" data-study-task="{unit["task"]}" data-study-hours="{unit["hours"]}"><h4>{unit["task"]} · '+bi(task['title'])+f' · {unit["hours"]} '+bi('ч изучения','learning h')+'</h4>',
                '<p>'+bi(unit['focus'])+'</p>',
                '<p class="small">'+', '.join(source_link(refs[r],prefix) for r in unit['sources'])+'</p>',
                '<p><b>'+bi('Проверка понимания: ','Understanding check: ')+'</b>'+bi(unit['mastery_check'])+'</p></div>']
    out += ['</div></details><p class="small"><a href="'+prefix+'library.html#foundation-path">'+bi('Связная последовательность фундаментальных тем','Connected foundation sequence')+'</a> · <a href="'+prefix+'learning-guides.md">'+bi('Практические пояснения к дополнениям','Practical notes for the additions')+'</a></p></div>']
    return ''.join(out)


def foundation_path(path, literature):
    refs = {r['id']:r for r in literature['references']}
    out = ['<!-- foundation-path --><section id="foundation-path"><h2>'+bi('Связная база робототехники','Connected robotics foundations')+'</h2>',
           '<p>'+bi(path['scope'])+'</p><p>'+bi(path['hours_policy'])+'</p><ol>']
    for step in path['steps']:
        out += [f'<li id="foundation-{step["id"]}"><h3>'+bi(step['title'])+'</h3>',
                '<p>'+', '.join(f'<a href="curriculum.html#{s}">{s}</a>' for s in step['stages'])+'</p>',
                '<p>'+bi(step['mastery_check'])+'</p>',
                '<p class="small">'+', '.join(source_link(refs[r]) for r in step['sources'])+'</p></li>']
    out += ['</ol><p>'+bi(path['limits'])+'</p><p><a href="learning-guides.md">'+bi('Пояснения и протоколы новых блоков','Notes and protocols for the new units')+'</a></p></section><!-- /foundation-path -->']
    return ''.join(out)


def reference_additions(literature):
    out = ['<!-- reference-additions --><section id="reference-additions"><h2>'+bi('Дополнения по проверке покрытия','Coverage-review additions')+'</h2>']
    for ref in literature['references']:
        if ref['id'] not in {'SW13','SW14','math-contact','math-qp','H-GAIT','H-TENDON-FRICTION'}:
            continue
        out += [f'<article class="panel anchor" id="ref-{ref["id"]}"><h3>'+bi(ref['title'])+'</h3>',
                '<p>'+html.escape(ref['authors'])+'</p>',
                '<p><a href="'+html.escape(ref['url'],quote=True)+'">'+bi('Открыть первичный источник','Open primary source')+'</a></p>',
                '<p>'+bi(ref['selection'])+'</p><p class="small">'+bi(ref['access'])+'</p>',
                '<p class="small">'+bi(ref['limitations'])+'</p>']
        for link in ref.get('links',[]):
            out.append('<p><a href="'+html.escape(link['url'],quote=True)+'">'+html.escape(link.get('title',link['url']))+'</a></p>')
        out.append('</article>')
    out.append('</section><!-- /reference-additions -->')
    return ''.join(out)


def library_stage_row(stage, item, route, literature):
    refs = {r['id']:r for r in literature['references']}
    start = date.fromisoformat(item['start']).strftime('%d.%m.%Y')
    links = '<br>'.join(f'<a href="#ref-{r["ref"]}">'+bi(refs[r['ref']]['title'])+'</a>' for r in route['readings'])
    return f'<tr><td><a href="curriculum.html#{stage}">{stage}</a> · {route["learn_hours"]} '+bi('ч','h')+f'</td><td><a href="months/{item["start"][:7]}.html#guide-{stage}">{start}</a></td><td>{links}</td></tr>'
