"""Static site integrity checks. Run: python3 tests/site_test.py"""
import json
import unittest
from datetime import date
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


class Page(HTMLParser):
    def __init__(self, path):
        super().__init__(convert_charrefs=True)
        self.path = path
        self.ids = []
        self.links = []
        self.root = {}
        self.buttons = {}
        self.in_title = False
        self.title = ''
        self.feed(path.read_text())

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'html':
            self.root = attrs
        if 'id' in attrs:
            self.ids.append(attrs['id'])
        if tag == 'a' and 'href' in attrs:
            self.links.append(attrs['href'])
        if tag in ('script', 'img') and 'src' in attrs:
            self.links.append(attrs['src'])
        if tag == 'link' and 'href' in attrs:
            self.links.append(attrs['href'])
        if tag == 'button' and 'data-lang' in attrs:
            self.buttons[attrs['data-lang']] = attrs.get('aria-pressed')
        if tag == 'title':
            self.in_title = True

    def handle_endtag(self, tag):
        if tag == 'title':
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.title += data


PAGES = {p.resolve(): Page(p) for p in ROOT.rglob('*.html')}


class SiteTests(unittest.TestCase):
    def test_english_defaults_and_titles_on_every_page(self):
        self.assertTrue(PAGES)
        for path, page in PAGES.items():
            with self.subTest(page=str(path.relative_to(ROOT))):
                self.assertEqual(page.root.get('lang'), 'en')
                self.assertEqual(page.title, page.root['data-en-title'])
                self.assertEqual(page.buttons, {'ru': 'false', 'en': 'true'})
                self.assertEqual(len(page.ids), len(set(page.ids)), 'Duplicate HTML IDs')

    def test_local_files_and_anchors(self):
        for path, page in PAGES.items():
            for href in page.links:
                parts = urlsplit(href)
                if parts.scheme or parts.netloc:
                    continue
                with self.subTest(page=str(path.relative_to(ROOT)), href=href):
                    target = (path.parent / unquote(parts.path)).resolve() if parts.path else path
                    if target.is_dir():
                        target = target / 'index.html'
                    self.assertTrue(target.is_file(), f'Missing file: {target}')
                    if parts.fragment and target in PAGES:
                        self.assertIn(unquote(parts.fragment), PAGES[target].ids)

    def test_procurement_budget_and_owned_assets(self):
        data = json.loads((ROOT / 'procurement.json').read_text())
        items = {item['id']: item for item in data['items']}
        self.assertEqual(len(items), len(data['items']))
        self.assertTrue({'MacBook Pro', 'Creality Print'}.issubset({x['name'] for x in data['owned']}))
        self.assertTrue(any(x['kind'] == 'printer' for x in data['owned']))
        self.assertTrue(all(x['purchase_quantity'] == 0 and x['ownership_confirmed'] for x in data['owned']))
        subtotal = Decimal('0')
        unpriced = 0
        for row in data['first_basket']:
            item = items[row['id']]
            self.assertGreater(row['quantity'], 0)
            if item['price'] is None:
                unpriced += 1
            else:
                self.assertEqual(item['currency'], 'UAH')
                subtotal += Decimal(str(item['price'])) * row['quantity']
        self.assertEqual(subtotal, Decimal(str(data['first_basket_subtotal_uah'])))
        self.assertEqual(unpriced, data['first_basket_unpriced_rows'])
        self.assertEqual(data['baseline_hours_unchanged'], 2960)
        page = PAGES[ROOT / 'procurement.html']
        for item in items.values():
            self.assertIn('item-' + item['id'], page.ids)
            for field in ['title', 'quantity_text', 'compatibility', 'timing'] + (['notes'] if any((item['notes'] or {}).values()) else []):
                self.assertTrue(item[field]['ru'].strip())
                self.assertTrue(item[field]['en'].strip())
        report = json.loads((ROOT / 'procurement-verification.json').read_text())
        self.assertEqual(report['product_rows'], len(items))
        self.assertEqual(report['first_basket_subtotal_uah'], float(subtotal))
        self.assertEqual(report['first_basket_unpriced_rows'], unpriced)

    def test_json_and_calendar_totals(self):
        for path in ROOT.glob('*.json'):
            with self.subTest(path=path.name):
                json.loads(path.read_text())
        schedule = json.loads((ROOT / 'schedule.json').read_text())
        self.assertEqual(schedule['base_hours'] + schedule['contingency_hours'], 2960)
        self.assertEqual(schedule['allocated_hours'], 2960)
        self.assertEqual(schedule['calendar_capacity_hours'], 3045)
        self.assertEqual(schedule['unallocated_hours'], 85)

    def test_procurement_component_costs_and_reuse(self):
        data = json.loads((ROOT / 'procurement.json').read_text())
        items = {item['id']: item for item in data['items']}
        researched = [item for item in items.values() if item.get('market')]
        self.assertEqual(len(researched), 38)
        self.assertEqual(data['first_basket_unpriced_rows'], 0)
        self.assertEqual(
            Decimal(str(data['first_basket_without_workplace_uah'])),
            Decimal(str(data['first_basket_subtotal_uah'])) - Decimal(str(items['wb-workplace']['price'])),
        )
        for item in researched:
            with self.subTest(item=item['id']):
                market = item['market']
                amounts = {}
                for component in market['components']:
                    reused = component.get('reused_from') or component.get('included_in')
                    if reused:
                        self.assertIn(reused, items)
                        self.assertNotEqual(reused, item['id'])
                        self.assertIsNone(component.get('unit_price'))
                        continue
                    self.assertGreater(component['quantity'], 0)
                    self.assertGreater(component['unit_price'], 0)
                    self.assertEqual(urlsplit(component['url']).scheme, 'https')
                    for field in ['name', 'availability', 'shipping_to_ukraine', 'evidence_note']:
                        self.assertTrue(component[field]['ru'].strip(), field)
                        self.assertTrue(component[field]['en'].strip(), field)
                    currency = component['currency']
                    amounts[currency] = amounts.get(currency, Decimal(0)) + Decimal(str(component['unit_price'])) * Decimal(str(component['quantity']))
                self.assertEqual({k: v.quantize(Decimal('.01')) for k, v in amounts.items()},
                                 {k: Decimal(str(v)) for k, v in market['totals'].items()})
                if len(amounts) == 1:
                    currency, amount = next(iter(amounts.items()))
                    self.assertEqual(item['currency'], currency)
                    self.assertEqual(Decimal(str(item['price'])), amount.quantize(Decimal('.01')))
                elif not amounts:
                    self.assertTrue(market['components'], 'Free rows must reference budgeted materials')
                    self.assertEqual(item['price'], 0)
                else:
                    self.assertIsNone(item['price'], 'Do not add different currencies together')
        page = (ROOT / 'procurement.html').read_text()
        self.assertNotIn('Request price', page)
        self.assertNotIn('Запросить цену', page)

    def test_procurement_reused_materials_are_available_before_use(self):
        data = json.loads((ROOT / 'procurement.json').read_text())
        items = {item['id']: item for item in data['items']}
        schedule = json.loads((ROOT / 'schedule.json').read_text())
        stage_dates = {}
        for segment in schedule['segments']:
            if segment['hours'] > 0:
                day = date.fromisoformat(segment['date'])
                stage = segment['item']
                stage_dates[stage] = min(day, stage_dates.get(stage, day))

        def references(value, path=''):
            if isinstance(value, dict):
                for key, child in value.items():
                    child_path = f'{path}.{key}'
                    if key in ('reused_from', 'included_in'):
                        yield child_path, child
                    else:
                        yield from references(child, child_path)
            elif isinstance(value, list):
                for index, child in enumerate(value):
                    yield from references(child, f'{path}[{index}]')

        for item in items.values():
            with self.subTest(item=item['id']):
                self.assertIn(item['stage'], stage_dates, 'First use must be an active scheduled stage')
            for field, source_id in references(item):
                with self.subTest(item=item['id'], field=field, source=source_id):
                    self.assertIn(source_id, items, 'Reused or included material must identify its budgeted source')
                    self.assertNotEqual(source_id, item['id'], 'An item cannot supply itself')
                    source_stage = items[source_id]['stage']
                    self.assertIn(source_stage, stage_dates)
                    self.assertIn(item['stage'], stage_dates)
                    self.assertLessEqual(
                        stage_dates[source_stage], stage_dates[item['stage']],
                        f'{source_id} first appears in {source_stage}, after {item["id"]} needs it in {item["stage"]}',
                    )

    def test_tail_dividers_have_budgeted_precision_resistors(self):
        items = {
            item['id']: item
            for item in json.loads((ROOT / 'procurement.json').read_text())['items']
        }
        # Twelve encoder signal dividers and six two-resistor ADC dividers
        # each need twelve of the relevant values, plus at least 20% spares.
        required_values = {
            'tail-encoder-interface': (4700, 6800),
            'tail-current-interface': (10000,),
        }
        for item_id, values in required_values.items():
            components = items[item_id]['market']['components']
            for resistance in values:
                with self.subTest(item=item_id, resistance_ohm=resistance):
                    matching = [part for part in components if part.get('resistance_ohm') == resistance]
                    self.assertTrue(matching, 'A general resistor assortment does not establish this value and tolerance')
                    quantity = Decimal(0)
                    for part in matching:
                        self.assertGreater(part['tolerance_percent'], 0)
                        self.assertLessEqual(part['tolerance_percent'], 1)
                        self.assertFalse(part.get('reused_from') or part.get('included_in'))
                        self.assertGreater(part['unit_price'], 0, 'Precision resistors must be included in the component budget')
                        self.assertEqual(urlsplit(part['url']).scheme, 'https')
                        quantity += Decimal(str(part['quantity']))
                    self.assertGreaterEqual(quantity, 15, 'Twelve installed resistors require at least three spares')

    def test_procurement_stage_precedes_first_physical_use(self):
        data = json.loads((ROOT / 'procurement.json').read_text())
        estimate = json.loads((ROOT / 'estimate.json').read_text())
        schedule = json.loads((ROOT / 'schedule.json').read_text())
        stage_dates = {}
        task_dates = {}
        for segment in schedule['segments']:
            if segment['hours'] <= 0:
                continue
            day = date.fromisoformat(segment['date'])
            stage = segment['item']
            stage_dates[stage] = min(day, stage_dates.get(stage, day))
            key = (stage, segment['task'])
            task_dates[key] = min(day, task_dates.get(key, day))

        for item in data['items']:
            for use in item.get('required_for', []):
                with self.subTest(item=item['id'], use=use):
                    self.assertIn(use['stage'], estimate['items'])
                    tasks = estimate['items'][use['stage']]['tasks']
                    matches = [
                        index for index, task in enumerate(tasks)
                        if use['task_ref'] in task.get('refs', [])
                    ]
                    self.assertEqual(len(matches), 1, 'Physical use must identify one existing task')
                    key = (use['stage'], matches[0])
                    self.assertIn(key, task_dates, 'Physical use must be scheduled')
                    self.assertLessEqual(
                        stage_dates[item['stage']], task_dates[key],
                        f'{item["id"]} is first planned in {item["stage"]}, after {use} needs it',
                    )


if __name__ == '__main__':
    unittest.main()
