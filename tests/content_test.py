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
    """The published calendar contract: nine weekday hours, five on Saturday."""
    return 9 if day.weekday() < 5 else 5 if day.weekday() == 5 else 0


def span(segments):
    return (
        min((part['date'], part['day_offset']) for part in segments),
        max((part['date'], part['day_offset'] + part['hours']) for part in segments),
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
                    self.assertEqual(task['hours'], sum(part['hours'] for part in task['segments']))
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
        self.assertEqual(sum(totals.values()), schedule['calendar_capacity_hours'])

    def test_calendar_has_no_gaps_overlaps_or_excess_daily_hours(self):
        schedule = self.schedule
        start, end = date.fromisoformat(schedule['start']), date.fromisoformat(schedule['deadline'])
        by_day = defaultdict(list)
        for part in schedule['segments']:
            day = date.fromisoformat(part['date'])
            self.assertLessEqual(start, day)
            self.assertLessEqual(day, end)
            self.assertEqual(part['week'], (day - start).days // 7 + 1)
            by_day[day].append(part)
        capacities = Counter()
        allocations = Counter()
        day = start
        while day <= end:
            with self.subTest(day=day.isoformat()):
                used = 0
                for part in sorted(by_day[day], key=lambda part: part['day_offset']):
                    self.assertEqual(part['day_offset'], used, 'Gap or overlap in active time')
                    used += part['hours']
                    if part['item'] != 'CAP':
                        allocations[day.strftime('%Y-%m')] += part['hours']
                self.assertEqual(used, daily_capacity(day))
                capacities[day.strftime('%Y-%m')] += daily_capacity(day)
            day += timedelta(days=1)
        self.assertEqual(sum(capacities.values()), schedule['calendar_capacity_hours'])
        self.assertEqual(schedule['calendar_finish'], end.isoformat())
        self.assertEqual(schedule['work_finish'], max(
            part['date'] for part in schedule['segments'] if part['item'] != 'CAP'))
        self.assertEqual(schedule['weeks'], (end - start).days // 7 + 1)
        self.assertEqual(divmod(sum(capacities.values()), 50),
                         (schedule['full_weeks'], schedule['final_partial_week_hours']))
        self.assertEqual(len(schedule['months']), len(capacities))
        for month in schedule['months']:
            key = f"{month['year']}-{month['month']:02}"
            self.assertEqual(month['capacity_hours'], capacities[key])
            self.assertEqual(month['allocated_hours'], allocations[key])

    def test_monthly_tasks_match_source_outcomes_and_segments(self):
        expected, actual = Counter(), Counter()
        for stage, item in self.items.items():
            for index, task in enumerate(item['tasks'], 1):
                for part in task['segments']:
                    expected[(part['date'][:7], part['week'], f'{stage}.{index}')] += part['hours']
        for month, page in self.month_pages.items():
            for block in page.tasks:
                task_id = block['attrs']['data-task']
                stage, index = task_id.rsplit('.', 1)
                with self.subTest(month=month, task=task_id):
                    task = self.items[stage]['tasks'][int(index) - 1]
                    self.assertEqual(int(block['attrs']['data-total-hours']), task['hours'])
                    part_hours = int(block['attrs']['data-part-hours'])
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
                hours = [0 if value == '—' else int(value)
                         for value in block['cells'][1:]]
                self.assertEqual(hours, [task[key] for key in (*CATEGORIES, 'hours')])
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
