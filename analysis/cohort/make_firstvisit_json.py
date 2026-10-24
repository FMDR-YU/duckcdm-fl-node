# -*- coding: utf-8 -*-
"""Write the circe cohort definition of the training cohort (published selection rules, first visit as index) from the v205
definition, so that duckcdm can compile the cohort that feeds the federated arm (response to internal review B2, 2026-10-24).

    python make_firstvisit_json.py            -> Cohort_OHDSI_CKD_firstvisit.json

Rules (sql/v205_firstvisit_cohort_duckdb.sql):
  index      first visit occurrence inside an observation period (circe: VisitOccurrence primary event, limit First)
  rule 1     age >= 19 at index (unchanged from v205)
  rule 2     two serum creatinine records at least 730 days apart anywhere in the record: a creatinine measurement (any time,
             observation period ignored) that has a correlated creatinine measurement starting at least 730 days later
  rule 3     no RRT procedure or condition on or before the index (unchanged from v205)
  rule 4     no implausible potassium or hemoglobin in the 365 days before the index (unchanged from v205)
  end        index + 730 days, truncated to the observation period (circe does the truncation)
"""
import copy
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, 'Cohort_OHDSI_CKD_v205.json')
DST = os.path.join(HERE, 'Cohort_OHDSI_CKD_firstvisit.json')


def main():
    v = json.load(open(SRC, encoding='utf-8'))
    d = copy.deepcopy(v)
    d['PrimaryCriteria'] = {'CriteriaList': [{'VisitOccurrence': {}}],
                            'ObservationWindow': {'PriorDays': 0, 'PostDays': 0},
                            'PrimaryCriteriaLimit': {'Type': 'First'}}
    d['QualifiedLimit'] = {'Type': 'First'}
    d['ExpressionLimit'] = {'Type': 'First'}
    rules = {r['name']: r for r in v['InclusionRules']}
    age = next(r for n, r in rules.items() if n.startswith('Age'))
    rrt = next(r for n, r in rules.items() if n.startswith('No RRT'))
    impl = next(r for n, r in rules.items() if n.startswith('No implausible'))
    creat = {
        'name': 'Serum creatinine: two records at least 730 days apart (any time in the record)',
        'expression': {'Type': 'ALL', 'DemographicCriteriaList': [], 'Groups': [], 'CriteriaList': [{
            'Criteria': {'Measurement': {'CodesetId': 1, 'CorrelatedCriteria': {
                'Type': 'ALL', 'DemographicCriteriaList': [], 'Groups': [], 'CriteriaList': [{
                    'Criteria': {'Measurement': {'CodesetId': 1}},
                    'StartWindow': {'Start': {'Days': 730, 'Coeff': 1}, 'End': {'Coeff': 1}, 'UseIndexEnd': False, 'UseEventEnd': False},
                    'RestrictVisit': False, 'IgnoreObservationPeriod': True, 'Occurrence': {'Type': 2, 'Count': 1}}]}}},
            'StartWindow': {'Start': {'Coeff': -1}, 'End': {'Coeff': 1}, 'UseIndexEnd': False, 'UseEventEnd': False},
            'RestrictVisit': False, 'IgnoreObservationPeriod': True, 'Occurrence': {'Type': 2, 'Count': 1}}]}}
    d['InclusionRules'] = [copy.deepcopy(age), creat, copy.deepcopy(rrt), copy.deepcopy(impl)]
    d['EndStrategy'] = {'DateOffset': {'DateField': 'StartDate', 'Offset': 730}}
    json.dump(d, open(DST, 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
    print('wrote', DST, '| rules:', [r['name'] for r in d['InclusionRules']])


if __name__ == '__main__':
    main()
