"""Render the bounded M07 gear introduction. Run with --check to detect stale pages."""
import argparse
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def bi(value):
    return ''.join(f'<span lang="{lang}">{html.escape(value[lang])}</span>'
                   for lang in ('ru', 'en'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    lesson = json.loads((ROOT / 'gear-basics.json').read_text())
    estimate = json.loads((ROOT / 'estimate.json').read_text())
    task = estimate['items']['M07']['tasks'][0]
    allocation = task['lesson']
    assert sum(lesson[k] for k in ('learn', 'build', 'verify')) == lesson['hours']
    for key in ('hours', 'learn', 'build', 'verify'):
        assert lesson[key] == allocation[key] <= task[key]

    detail = f'<div class="anchor" id="{lesson["id"]}"><h3>{bi(lesson["title"])}</h3>'
    detail += f'<p class="small">{bi(lesson["budget"])}</p>'
    for step in lesson['steps']:
        detail += f'<h4>{bi(step["title"])}</h4><p>{bi(step["text"])}</p>'
    detail += f'<p>{bi(lesson["rig"])}</p><p>{bi(lesson["scope"])}</p>'
    detail += '<h4>' + bi({'ru': 'Схемы, видео и чтение', 'en': 'Diagrams, video and reading'}) + '</h4><ul>'
    for source in lesson['sources']:
        detail += f'<li><a href="{html.escape(source["url"], quote=True)}">{html.escape(source["title"])}</a></li>'
    detail += '</ul></div>'
    label = bi({'ru': 'Шестерёнки и редукторы · 6 ч внутри A1 →',
                'en': 'Gears and gearboxes · 6 h within A1 →'})
    note = '<div class="note"><h3>' + bi({
        'ru': '16 октября 2026: устройство передач перед стендом M07',
        'en': '16 October 2026: gear fundamentals before the M07 rig'}) + '</h3>'
    note += f'<p>{bi(lesson["budget"])}</p><a href="curriculum.html#M07-gears">{label}</a></div>'
    outputs = {
        'curriculum.html': (detail, '<div class="reading-route" data-reading-stage="M07">'),
        'months/2027-01.html': (
            f'<p><a href="../curriculum.html#M07-gears">{label}</a></p>',
            '<div class="reading-route" data-reading-stage="M07">'),
        'library.html': (
            f'<div class="note"><a href="curriculum.html#M07-gears">{label}</a></div>',
            '<main class="main">'),
        'changes.html': (note, '<div class="note" data-optional-project="TAIL_PCB">'),
    }
    stale = []
    for name, (content, anchor) in outputs.items():
        path = ROOT / name
        current = path.read_text()
        block = '<!-- gear-basics:start -->' + content + '<!-- gear-basics:end -->'
        if '<!-- gear-basics:start -->' in current:
            updated, count = re.subn(r'<!-- gear-basics:start -->.*?<!-- gear-basics:end -->',
                                    lambda _: block, current, flags=re.S)
            assert count == 1, name
        else:
            assert current.count(anchor) == 1, name
            replacement = anchor + block if name == 'library.html' else block + anchor
            updated = current.replace(anchor, replacement, 1)
        if current != updated:
            stale.append(name)
            if not args.check:
                path.write_text(updated)
    if args.check and stale:
        raise SystemExit('Stale gear introduction: ' + ', '.join(stale))
    print('Gear introduction is current.' if args.check else 'Rendered gear introduction.')


if __name__ == '__main__':
    main()
