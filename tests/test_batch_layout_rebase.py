from __future__ import annotations

import subprocess
import sys
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class BatchLayoutRebaseRegressionTests(unittest.TestCase):
    def test_layout_rebase_and_profile_extension_contract(self) -> None:
        probe = textwrap.dedent(
            r'''
            import copy
            import sys
            sys.path.insert(0, 'tools')
            import run_process_batch_request as r

            def page():
                return {
                    'id':'p','name':{'en':'P','zh':'P'},
                    'path':{'en':'p.html','zh':'zh/p.html'},
                    'order':0,'show_in_navigation':True,
                }

            def category(cid='c'):
                return {
                    'id':cid,'page_id':'p','kind':'conference',
                    'label':{'en':cid,'zh':cid},'title':{'en':cid,'zh':cid},
                    'intro':{'en':'','zh':''},'order':0,
                    'show_on_web':True,'show_on_cv':True,
                }

            def layout(assignments, placements=None, categories=None):
                return {
                    'pages':[page()],
                    'categories':categories or [category()],
                    'cv_category_order':['c'],
                    'assignments':copy.deepcopy(assignments),
                    'placements':copy.deepcopy(placements or {key:[] for key in assignments}),
                    'dossier_category_order':['c'],
                }

            # Unrelated item churn must not look like a stale reorder.
            expected = layout({
                'A':{'category_id':'c','order':0},
                'B':{'category_id':'c','order':1},
            })
            current = layout({
                'A':{'category_id':'c','order':0},
                'X':{'category_id':'c','order':1},
                'B':{'category_id':'c','order':2},
            })
            assert r.layout_expected_matches(current, expected)

            # A real shared-ID reorder must still be detected.
            changed = layout({
                'B':{'category_id':'c','order':0},
                'X':{'category_id':'c','order':1},
                'A':{'category_id':'c','order':2},
            })
            assert not r.layout_expected_matches(changed, expected)

            # Rebase a genuine requested reorder without losing current-only X.
            requested = layout({
                'B':{'category_id':'c','order':0},
                'A':{'category_id':'c','order':1},
            })
            rebased = r.rebase_layout_bundle(current, requested)
            assert set(rebased['assignments']) == {'A','B','X'}
            sequence = [iid for iid, kind in r._layout_refs(r._canonical_layout(rebased), 'c') if kind == 'primary']
            assert sequence.index('B') < sequence.index('A')
            assert 'X' in sequence

            # An item already deleted from current data is dropped from the stale request.
            current2 = layout({'A':{'category_id':'c','order':0}})
            requested2 = layout({
                'A':{'category_id':'c','order':0},
                'OLD':{'category_id':'c','order':1},
            })
            rebased2 = r.rebase_layout_bundle(current2, requested2)
            assert set(rebased2['assignments']) == {'A'}

            # Never delete a category that gained an unseen current item/reference.
            current3 = layout(
                {'A':{'category_id':'c','order':0}, 'X':{'category_id':'gone','order':0}},
                categories=[category('c'), category('gone')],
            )
            requested3 = layout({'A':{'category_id':'c','order':0}}, categories=[category('c')])
            try:
                r.rebase_layout_bundle(current3, requested3)
            except ValueError as exc:
                assert 'gained item X' in str(exc)
            else:
                raise AssertionError('unsafe category deletion was allowed')

            # Placement stale checks compare relative shared order, not absolute numbers.
            expected4 = layout(
                {'A':{'category_id':'c','order':0}, 'B':{'category_id':'c','order':1}},
                {'A':[{'category_id':'d','order':0}], 'B':[{'category_id':'d','order':1}]},
                [category('c'), category('d')],
            )
            current4 = layout(
                {
                    'A':{'category_id':'c','order':0},
                    'B':{'category_id':'c','order':1},
                    'X':{'category_id':'c','order':2},
                },
                {
                    'A':[{'category_id':'d','order':0}],
                    'X':[{'category_id':'d','order':1}],
                    'B':[{'category_id':'d','order':2}],
                },
                [category('c'), category('d')],
            )
            assert r.layout_expected_matches(current4, expected4)
            changed4 = copy.deepcopy(current4)
            changed4['placements']['A'][0]['order'] = 2
            changed4['placements']['B'][0]['order'] = 0
            assert not r.layout_expected_matches(changed4, expected4)

            # The extension operation emitted by admin/personal-profile.js must be valid.
            r.validate_operation({'op':'personal_profile','before':{},'after':{}})
            try:
                r.validate_operation({'op':'personal_profile','before':{},'after':None})
            except ValueError:
                pass
            else:
                raise AssertionError('invalid personal_profile operation accepted')
            '''
        )
        completed = subprocess.run(
            [sys.executable, '-c', probe],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)


if __name__ == '__main__':
    unittest.main()
