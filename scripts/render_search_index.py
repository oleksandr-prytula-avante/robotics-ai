"""Index public page titles and anchored headings for offline site search."""
import argparse
import json
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / 'assets/search-index.js'
VOID_TAGS = set('area base br col embed hr img input link meta param source track wbr'.split())
HEADING_TAGS = {'h1', 'h2', 'h3', 'summary'}


class SearchPage(HTMLParser):
    def __init__(self, path):
        super().__init__()
        self.path = path.relative_to(ROOT).as_posix()
        self.stack = []
        self.heading = None
        self.title = {}
        self.sections = {}
        self.feed(path.read_text())

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'html':
            self.title = {lang: attrs.get(f'data-{lang}-title', '').split(' · ')[0]
                          for lang in ('ru', 'en')}
        if tag not in VOID_TAGS:
            self.stack.append((tag, attrs))
        if tag not in HEADING_TAGS or not any(node == 'main' for node, _ in self.stack):
            return
        anchor = next((item['id'] for _, item in reversed(self.stack) if 'id' in item), '')
        if anchor and anchor != 'main' and anchor not in self.sections:
            self.heading = (tag, anchor, {'ru': [], 'en': []})

    def handle_data(self, data):
        if self.heading:
            lang = next((item['lang'] for tag, item in reversed(self.stack)
                         if tag != 'html' and item.get('lang') in {'ru', 'en'}), None)
            # Bilingual inline spans override the document's default language.
            for language in (lang,) if lang else ('ru', 'en'):
                self.heading[2][language].append(data)

    def handle_endtag(self, tag):
        if self.heading and self.heading[0] == tag:
            _, anchor, localized = self.heading
            labels = {lang: ' '.join(''.join(text).split()) for lang, text in localized.items()}
            if any(labels.values()):
                self.sections[anchor] = labels
            self.heading = None
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break

    def entries(self):
        yield [self.path, self.title['ru'], self.title['en']]
        for anchor, labels in self.sections.items():
            yield [f'{self.path}#{anchor}', labels['ru'] or labels['en'], labels['en'] or labels['ru']]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    paths = sorted([*ROOT.glob('*.html'), *ROOT.glob('months/*.html'),
                    *ROOT.glob('source-library/*.html')])
    pages = [SearchPage(path) for path in paths]
    entries = [entry for page in pages for entry in page.entries()]
    content = 'window.roboticsSearchIndex = ' + json.dumps(entries, ensure_ascii=False, separators=(',', ':')) + ';\n'
    if args.check:
        if not DESTINATION.exists() or DESTINATION.read_text() != content:
            raise SystemExit('Site search index is stale. Run python3 scripts/render_search_index.py')
    else:
        DESTINATION.write_text(content)
    print(f'Indexed {len(entries)} links across {len(pages)} pages.')


if __name__ == '__main__':
    main()
