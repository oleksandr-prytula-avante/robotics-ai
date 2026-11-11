"""Source, schedule and rendered-content checks. Run: python3 tests/content_test.py."""
import json
import re
import unittest
from collections import Counter, defaultdict
from datetime import date, timedelta
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CATEGORIES = ('learn', 'build', 'verify')
DERIVED_TASK_FIELDS = {'segments', 'start', 'end'}


def read_json(name):
    return json.loads((ROOT / name).read_text())


def daily_capacity(day):
    """Exact minutes: eight hours twenty minutes, Monday through Saturday."""
    days_off = {date(2028, 12, 31)}
    return 500 if day.weekday() < 6 and day not in days_off else 0


def span(segments):
    return (
        min((part['date'], part['day_offset_minutes']) for part in segments),
        max((part['date'], part['day_offset_minutes'] + part['minutes']) for part in segments),
    )


class ContentBlocks(HTMLParser):
    """Collect task and reading blocks without a browser or third-party parser."""
    VOID_TAGS = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input',
                 'link', 'meta', 'param', 'source', 'track', 'wbr'}

    def __init__(self, path):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.week = None
        self.active = []
        self.tasks = []
        self.readings = []
        self.feed(path.read_text())

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'h2' and attrs.get('id', '').startswith('week-'):
            self.week = int(attrs['id'][5:])
        if tag not in self.VOID_TAGS:
            self.depth += 1
        if tag in {'div', 'tr'} and ('data-task' in attrs or 'data-reading-stage' in attrs):
            self.active.append({'attrs': attrs, 'depth': self.depth,
                                'week': self.week, 'text': [], 'refs': [],
                                'cells': [], 'in_cell': False})
        if tag == 'td':
            for block in self.active:
                if 'data-task' in block['attrs']:
                    block['cells'].append([])
                    block['in_cell'] = True
        if 'data-reading-ref' in attrs:
            for block in self.active:
                if 'data-reading-stage' in block['attrs']:
                    block['refs'].append(attrs['data-reading-ref'])

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID_TAGS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag in self.VOID_TAGS:
            return
        if tag == 'td':
            for block in self.active:
                block['in_cell'] = False
        if self.active and self.active[-1]['depth'] == self.depth:
            block = self.active.pop()
            block['text'] = ''.join(block['text'])
            block['cells'] = [''.join(cell) for cell in block['cells']]
            target = self.tasks if 'data-task' in block['attrs'] else self.readings
            target.append(block)
        self.depth -= 1

    def handle_data(self, data):
        for block in self.active:
            block['text'].append(data)
            if block['in_cell']:
                block['cells'][-1].append(data)


class ContentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schedule = read_json('schedule.json')
        cls.estimate = read_json('estimate.json')
        cls.literature = read_json('literature.json')
        cls.items = {item['id']: item for item in cls.schedule['items']}
        cls.month_pages = {
            Path(month['page']).stem: ContentBlocks(ROOT / month['page'])
            for month in cls.schedule['months']
        }

    def test_active_estimate_matches_scheduled_tasks(self):
        self.assertEqual(list(self.items), self.estimate['order'])
        for stage, item in self.items.items():
            with self.subTest(stage=stage):
                source = self.estimate['items'][stage]
                self.assertEqual(item['hours'], source['base'])
                self.assertEqual(
                    [{key: value for key, value in task.items()
                      if key not in DERIVED_TASK_FIELDS} for task in item['tasks']],
                    source['tasks'],
                )
        self.assertEqual(self.schedule['calendar_assumptions'],
                         self.estimate['calendar_assumptions'])

    def test_task_segment_and_category_accounting(self):
        totals = Counter()
        flattened = []
        for stage, item in self.items.items():
            with self.subTest(stage=stage):
                self.assertEqual(item['hours'], sum(task['hours'] for task in item['tasks']))
                self.assertEqual(item['segments'],
                                 [part for task in item['tasks'] for part in task['segments']])
                for index, task in enumerate(item['tasks']):
                    self.assertTrue(task['segments'])
                    self.assertEqual(round(task['hours'] * 60), sum(part['minutes'] for part in task['segments']))
                    self.assertEqual((task['start'], task['end']),
                                     (span(task['segments'])[0][0], span(task['segments'])[1][0]))
                    for part in task['segments']:
                        self.assertEqual((part['item'], part['task']), (stage, index))
                        self.assertGreater(part['hours'], 0)
                    if item['track'] not in {'reserve', 'capacity'}:
                        self.assertEqual(task['hours'], sum(task[key] for key in CATEGORIES))
                    else:
                        self.assertEqual(sum(task[key] for key in CATEGORIES), 0)
                totals[item['track']] += item['hours']
                flattened.extend(item['segments'])
        schedule = self.schedule
        self.assertEqual(flattened, schedule['segments'])
        core = sum(value for key, value in totals.items() if key not in {'reserve', 'capacity'})
        self.assertEqual(core, schedule['base_hours'])
        self.assertEqual(totals['reserve'], schedule['contingency_hours'])
        self.assertEqual(totals['capacity'], schedule['unallocated_hours'])
        self.assertEqual(core + totals['reserve'], schedule['allocated_hours'])
        self.assertEqual(sum(round(value * 60) for value in totals.values()), schedule['calendar_capacity_minutes'])

    def test_calendar_has_no_gaps_overlaps_or_excess_daily_hours(self):
        schedule = self.schedule
        start, end = date.fromisoformat(schedule['start']), date.fromisoformat(schedule['deadline'])
        by_day = defaultdict(list)
        for part in schedule['segments']:
            day = date.fromisoformat(part['date'])
            self.assertLessEqual(start, day)
            self.assertLessEqual(day, end)
            self.assertEqual(part['week'], (day - date.fromisoformat(schedule['week_start'])).days // 7 + 1)
            by_day[day].append(part)
        capacities = Counter()
        allocations = Counter()
        day = start
        while day <= end:
            with self.subTest(day=day.isoformat()):
                used = 0
                for part in sorted(by_day[day], key=lambda part: part['day_offset_minutes']):
                    self.assertEqual(part['day_offset_minutes'], used, 'Gap or overlap in active time')
                    used += part['minutes']
                    if part['item'] != 'CAP':
                        allocations[day.strftime('%Y-%m')] += part['minutes']
                self.assertEqual(used, daily_capacity(day))
                capacities[day.strftime('%Y-%m')] += daily_capacity(day)
            day += timedelta(days=1)
        self.assertEqual(sum(capacities.values()), schedule['calendar_capacity_minutes'])
        self.assertEqual(schedule['calendar_finish'], max(part['date'] for part in schedule['segments']))
        self.assertEqual(schedule['excluded_dates'], ['2028-12-31'])
        self.assertEqual(schedule['work_finish'], max(
            part['date'] for part in schedule['segments'] if part['item'] != 'CAP'))
        self.assertEqual(schedule['weeks'], (end - date.fromisoformat(schedule['week_start'])).days // 7 + 1)
        self.assertEqual(sum(capacities.values()), schedule['full_weeks'] * 3000 +
                         schedule['first_partial_week_minutes'] + schedule['final_partial_week_minutes'] -
                         schedule['interior_excluded_minutes'])
        self.assertEqual(len(schedule['months']), len(capacities))
        for month in schedule['months']:
            key = f"{month['year']}-{month['month']:02}"
            self.assertEqual(month['capacity_minutes'], capacities[key])
            self.assertEqual(month['allocated_minutes'], allocations[key])

    def test_completion_and_buffer_are_separate(self):
        schedule = self.schedule
        self.assertEqual(schedule['start'], '2028-01-02')
        self.assertEqual(schedule['work_finish'], '2028-12-30')
        self.assertEqual(schedule['deadline'], '2028-12-31')
        self.assertEqual(schedule['buffer_minutes'], 0)
        self.assertEqual(schedule['allocated_minutes'], 2600 * 60)
        self.assertFalse(any(item['track'] == 'reserve' for item in schedule['items']))
        self.assertFalse(any(part['item'] == 'CAP' for part in schedule['segments']))

    def test_individual_review_covers_every_task_and_preserves_new_learning(self):
        report = read_json('task-hour-review.json')
        rows = {row['key']: row for row in report['tasks']}
        expected = {f'{stage}.{index}': task
                    for stage, item in self.items.items()
                    if item['track'] not in {'reserve', 'capacity'}
                    for index, task in enumerate(item['tasks'], 1)}
        self.assertEqual(set(rows), set(expected))
        self.assertEqual(len(rows), len(report['tasks']))
        for key, task in expected.items():
            row = rows[key]
            with self.subTest(task=key):
                self.assertEqual(row['after'], {c: task[c] for c in CATEGORIES})
                self.assertTrue(row['reason'].strip())
                if row['stage'] != 'M01':
                    self.assertGreaterEqual(task['learn'], row['pre_compression_learn'])
        self.assertNotIn('timeline_compression', self.estimate)
        self.assertEqual(report['base_hours'], self.schedule['base_hours'])
        self.assertEqual(report['category_hours'], {
            c: sum(task[c] for task in expected.values()) for c in CATEGORIES})
        for stage, item in self.items.items():
            for category in CATEGORIES:
                self.assertEqual(self.estimate['items'][stage][category],
                                 sum(t[category] for t in item['tasks']))

    def test_trial_counts_and_physical_acceptance_remain_in_the_plan(self):
        arm = self.items['A3']['tasks']
        self.assertIn('30 детерминированных', arm[1]['result']['ru'])
        self.assertIn('500 г', arm[1]['result']['ru'])
        self.assertIn('100 циклов', arm[2]['result']['ru'])
        self.assertIn('каждые 25', arm[2]['result']['ru'])
        self.assertIn('100 циклов', self.items['T3']['tasks'][1]['result']['ru'])
        self.assertIn('40 попыток', self.items['M23']['tasks'][4]['result']['ru'])
        self.assertIn('30–50+', self.items['M22']['tasks'][4]['result']['ru'])
        self.assertIn('F1–F10', self.items['M06']['tasks'][4]['result']['ru'])

    def test_current_stage_headings_use_active_hours(self):
        source = (ROOT / 'curriculum.html').read_text()
        for stage, item in self.items.items():
            block = re.search(r'<section\b[^>]*id="'+re.escape(stage)+r'".*?</section>', source, re.S)
            self.assertIsNotNone(block, stage)
            self.assertIn(f'{item["hours"]} h · {date.fromisoformat(item["start"]):%d.%m.%Y}', block[0])
        for path in [ROOT / 'method.html', ROOT / 'index.html', *ROOT.glob('months/2028-*.html')]:
            text = path.read_text()
            self.assertNotIn('120 ч чтения и целевого изучения сняты', text, path.name)

    def test_material_dates_match_their_scheduled_tasks(self):
        for condition in self.schedule['calendar_assumptions']['material_ready_conditions']:
            item = self.items[condition['stage']]
            task = item['tasks'][condition['task_index']]
            self.assertEqual(condition['nominal_slot_start'], task['start'])
            self.assertEqual(condition['nominal_gate_finish'], item['tasks'][0]['end'])
            self.assertEqual(task['material_ready_condition'], condition['condition'])

    def test_monthly_tasks_match_source_outcomes_and_segments(self):
        expected, actual = Counter(), Counter()
        for stage, item in self.items.items():
            for index, task in enumerate(item['tasks'], 1):
                for part in task['segments']:
                    expected[(part['date'][:7], part['week'], f'{stage}.{index}')] += part['minutes']
        for month, page in self.month_pages.items():
            for block in page.tasks:
                task_id = block['attrs']['data-task']
                stage, index = task_id.rsplit('.', 1)
                with self.subTest(month=month, task=task_id):
                    task = self.items[stage]['tasks'][int(index) - 1]
                    self.assertEqual(int(block['attrs']['data-total-minutes']), round(task['hours'] * 60))
                    part_hours = int(block['attrs']['data-part-minutes'])
                    self.assertGreater(part_hours, 0)
                    actual[(month, block['week'], task_id)] += part_hours
                    for field in ('title', 'result', 'material_ready_condition'):
                        for language, value in task.get(field, {}).items():
                            self.assertIn(value, block['text'], f'{field}/{language} is stale or missing')
        self.assertEqual(actual, expected)

    def test_curriculum_tasks_match_source_hours_and_material_conditions(self):
        page = ContentBlocks(ROOT / 'curriculum.html')
        expected = {
            f'{stage}.{index}': task
            for stage, item in self.items.items()
            for index, task in enumerate(item['tasks'], 1)
        }
        self.assertEqual(Counter(block['attrs']['data-task'] for block in page.tasks),
                         Counter({task_id: 1 for task_id in expected}))
        for block in page.tasks:
            task_id = block['attrs']['data-task']
            with self.subTest(task=task_id):
                task = expected[task_id]
                self.assertEqual(len(block['cells']), 5)
                minutes = [0 if value == '—' else
                           (int(value.split(':')[0]) * 60 + int(value.split(':')[1]) if ':' in value else int(value) * 60)
                           for value in block['cells'][1:]]
                self.assertEqual(minutes, [round(task[key] * 60) for key in (*CATEGORIES, 'hours')])
                for field in ('title', 'result', 'material_ready_condition'):
                    for language, value in task.get(field, {}).items():
                        self.assertIn(value, block['cells'][0],
                                      f'{field}/{language} is stale or missing')

    def test_reading_routes_references_and_hours_match(self):
        routes = self.literature['routes']
        expected_stages = {stage for stage, item in self.items.items()
                           if sum(task['learn'] for task in item['tasks']) > 0}
        self.assertEqual(set(routes), expected_stages)
        self.assertEqual(self.literature['learning_hours_total'],
                         sum(route['learn_hours'] for route in routes.values()))
        pages = {'curriculum': ContentBlocks(ROOT / 'curriculum.html'), **self.month_pages}
        for name, page in pages.items():
            expected = set(routes) if name == 'curriculum' else {
                part['item'] for part in self.schedule['segments']
                if part['date'].startswith(name) and part['item'] in routes
            }
            self.assertEqual(Counter(block['attrs']['data-reading-stage'] for block in page.readings),
                             Counter({stage: 1 for stage in expected}))
            for block in page.readings:
                stage = block['attrs']['data-reading-stage']
                with self.subTest(page=name, stage=stage):
                    route = routes[stage]
                    hours = sum(task['learn'] for task in self.items[stage]['tasks'])
                    self.assertEqual(route['learn_hours'], hours)
                    self.assertEqual(block['refs'], [reading['ref'] for reading in route['readings']])
                    match = re.search(r'Learning for the complete stage: (\d+) h', block['text'])
                    self.assertIsNotNone(match)
                    self.assertEqual(int(match[1]), hours)
                    for reading in route['readings']:
                        for text in reading['selection'].values():
                            self.assertIn(text,block['text'])
                    for unit in route.get('study_units',[]):
                        for field in ('focus','mastery_check'):
                            for text in unit[field].values():
                                self.assertIn(text,block['text'])

    def test_every_learning_hour_has_a_task_source_and_understanding_check(self):
        references = {r['id']:r for r in self.literature['references']}
        self.assertEqual(len(references),len(self.literature['references']))
        units = {}
        for stage,route in self.literature['routes'].items():
            self.assertEqual(sum(u['hours'] for u in route['study_units']),route['learn_hours'])
            assigned = {r['ref'] for r in route['readings']}
            self.assertTrue(assigned <= set(references))
            for unit in route['study_units']:
                key = unit['task']
                with self.subTest(task=key):
                    self.assertNotIn(key,units)
                    units[key] = unit
                    owner,index = key.rsplit('.',1)
                    self.assertEqual(owner,stage)
                    task = self.items[stage]['tasks'][int(index)-1]
                    self.assertEqual(unit['hours'],task['learn'])
                    self.assertEqual(unit['mastery_check'],task.get('result') or task['title'])
                    self.assertTrue(set(unit['sources']) <= assigned)
                    self.assertTrue(unit['sources'])
                    for language in ('ru','en'):
                        self.assertTrue(unit['focus'][language].strip())
        expected = {f'{stage}.{index}' for stage,item in self.items.items()
                    for index,t in enumerate(item['tasks'],1) if t['learn']}
        self.assertEqual(set(units),expected)
        self.assertEqual(sum(u['hours'] for u in units.values()),701)
        required = {
            'M11.2': {'SW13'}, 'M14.1': {'SW05','SW14'},
            'M10.6': {'math-feedback'}, 'M13.5': {'math-contact'},
            'M19.7': {'math-qp','math-convex'}, 'M19.3': {'H-GAIT'},
            'T1.3': {'H-SLOCUM','H-TENDON-FRICTION'},
            'T2.3': {'H-TENDON-FRICTION'}, 'D2.2': {'math-contact'},
        }
        for key,sources in required.items():
            self.assertTrue(sources <= set(units[key]['sources']),key)

    def test_foundation_path_connects_real_stages_and_sources(self):
        path = read_json('learning-path.json')
        refs = {r['id'] for r in self.literature['references']}
        self.assertEqual(len({step['id'] for step in path['steps']}),len(path['steps']))
        self.assertEqual(len(path['steps']),9)
        for step in path['steps']:
            self.assertTrue(set(step['stages']) <= set(self.items))
            self.assertTrue(set(step['sources']) <= refs)
            self.assertTrue(all(step['mastery_check'].values()))
        self.assertIn('id="foundation-path"',(ROOT / 'library.html').read_text())
        self.assertTrue((ROOT / 'learning-guides.md').is_file())

    def test_internal_prerequisites_finish_before_dependent_work(self):
        hardware = self.estimate['reports']['hardware']
        hardware_rows = hardware['rows'] + hardware['retained_projects']
        reference_owners = {task['id']: row['id'] for row in hardware_rows for task in row['tasks']}
        nodes, parents = {}, defaultdict(list)
        for stage, item in self.items.items():
            nodes[stage] = span(item['segments'])
            if item.get('parent'):
                parents[item['parent']].extend(item['segments'])
            for task in item['tasks']:
                bounds = span(task['segments'])
                if task.get('id'):
                    nodes[task['id']] = bounds
                    nodes[f"{stage}.{task['id']}"] = bounds
                for reference in task.get('refs', []):
                    if reference in reference_owners:
                        nodes[f'{reference_owners[reference]}.{reference}'] = bounds
        nodes.update({parent: span(parts) for parent, parts in parents.items()})
        for report in self.estimate['reports'].values():
            for alias, stage in report.get('module_aliases', {}).items():
                nodes[alias] = nodes[stage]

        # Named competency entries describe scope in prose; these bindings identify
        # their scheduled providers. Explicit JSON competency aliases take priority.
        competencies = {
            'P_UNITS': ['M02-A'], 'P_GEOMETRY': ['M02', 'M08'],
            'P_KIN3': ['M08'], 'P_LIMITED_CONTROL': ['M07.A3'],
            'P_ROS': ['S2'], 'P_HIL': ['M13'], 'P_CRAWL': ['M19'],
            'P_ARM_MODEL': ['M08', 'M09', 'M10'], 'P_LINEAR_ALG': ['M02'],
            'P_PLANNING': ['M16', 'M17'],
            **hardware['competency_aliases'],
        }
        for alias, providers in competencies.items():
            nodes[alias] = (min(nodes[source][0] for source in providers),
                            max(nodes[source][1] for source in providers))
        external = {}
        for gate in hardware['gate_aliases']:
            if gate['owner'].startswith('procurement.'):
                external[gate['id']] = gate['owner'].split('.', 1)[1]
            else:
                nodes[gate['id']] = nodes[gate['owner']]
        procurement_ids = {entry['id'] for entry in hardware['procurement']}
        edges = []
        for row in hardware_rows:
            for task in row['tasks']:
                edges.extend((dependency, f"{row['id']}.{task['id']}")
                             for dependency in task.get('required_prerequisites', []))
        for owner in ('math', 'software'):
            for row in self.estimate['reports'][owner]['rows']:
                edges.extend((dependency, row['id']) for dependency in row.get('prerequisites', []))
                for phase in row.get('execution_segments', []):
                    edges.extend((dependency, phase['id']) for dependency in phase['prerequisites'])
        self.assertTrue(edges)
        for dependency, target in edges:
            with self.subTest(dependency=dependency, target=target):
                if dependency in external:
                    # A future receipt is a condition, not a verified delivery.
                    self.assertIn(external[dependency], procurement_ids)
                    continue
                self.assertIn(dependency, nodes)
                self.assertIn(target, nodes)
                self.assertLessEqual(nodes[dependency][1], nodes[target][0])


if __name__ == '__main__':
    unittest.main()
