"""Optional forecast accounting, calendar boundaries and rendered-source checks."""
import sys
import unittest
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from render_growth_timeline import allocate, build_model, hours_range, next_monday, outputs, read


class GrowthTimelineTests(unittest.TestCase):
    def test_ranges_include_every_source_format(self):
        self.assertEqual(hours_range({'id':'a','hours':10}), (10,10))
        self.assertEqual(hours_range({'id':'b','approx_extra_hours_range':[20,40]}), (20,40))
        self.assertEqual(hours_range({'id':'c','approximate_extra_hours_range':{'low':30,'high':55}}), (30,55))
        with self.assertRaises(ValueError):
            hours_range({'id':'bad','approx_extra_hours_range':[40,20]})

    def test_partial_days_and_weekend_are_allocated_without_gaps(self):
        plan=allocate([{'id':'a','minutes':550},{'id':'b','minutes':650}], date(2028,1,8),500,[0,1,2,3,4,5])
        self.assertEqual(plan['tracks'][0]['end'], '2028-01-10')
        self.assertEqual(plan['tracks'][1]['start'], '2028-01-10')
        self.assertEqual(plan['tracks'][1]['end'], '2028-01-11')
        self.assertEqual([(s['date'],s['day_offset_minutes'],s['minutes']) for s in plan['segments']],
                         [('2028-01-08',0,500),('2028-01-10',0,50),('2028-01-10',50,450),('2028-01-11',0,200)])

    def test_exclusions_and_exact_day_finish(self):
        plan=allocate([{'id':'a','minutes':500},{'id':'b','minutes':1}],date(2028,1,3),500,[0,1,2,3,4,5],['2028-01-04'])
        self.assertEqual(plan['tracks'][0]['end'],'2028-01-03')
        self.assertEqual(plan['tracks'][1]['start'],'2028-01-05')
        self.assertEqual(next_monday(date(2027,12,31)),date(2028,1,3))
        self.assertEqual(next_monday(date(2028,1,3)),date(2028,1,10))

    def test_both_scenarios_account_for_all_tracks_and_capacity(self):
        source=read('development-map.json')
        config=read('growth-timeline-config.json')
        core=read('schedule.json')
        model=build_model(source,config,core)
        self.assertEqual(model['start'],'2028-01-03')
        for scenario,total in [('low',865),('high',1455)]:
            plan=model['scenarios'][scenario]
            self.assertEqual(Counter(t['id'] for t in plan['tracks']),Counter(t['id'] for t in source['tracks']))
            self.assertEqual(plan['total_minutes'],total*60)
            self.assertEqual(sum(p['minutes'] for p in plan['segments']),total*60)
            by_day=defaultdict(list)
            for part in plan['segments']:
                self.assertIn(date.fromisoformat(part['date']).weekday(),config['workdays'])
                self.assertGreater(part['date'],core['calendar_finish'])
                by_day[part['date']].append(part)
            for day,parts in by_day.items():
                position=0
                for part in parts:
                    self.assertEqual(part['day_offset_minutes'],position)
                    position+=part['minutes']
                self.assertLessEqual(position,500)
                if day!=plan['end']:
                    self.assertEqual(position,500)
            seen=set()
            for track in plan['tracks']:
                self.assertTrue(set(track['dependencies'])<=seen)
                seen.add(track['id'])

    def test_missing_tracks_and_reversed_dependencies_are_rejected(self):
        source,config,core=read('development-map.json'),read('growth-timeline-config.json'),read('schedule.json')
        config['groups'][0]['tracks'].pop()
        with self.assertRaises(ValueError):
            build_model(source,config,core)
        config=read('growth-timeline-config.json')
        for group in config['groups']:
            group['tracks'].reverse()
        with self.assertRaises(ValueError):
            build_model(source,config,core)

    def test_generated_forecast_and_page_are_current(self):
        for filename,expected in outputs().items():
            self.assertEqual((ROOT/filename).read_text(),expected,filename)


if __name__=='__main__':
    unittest.main()
