"""Exercise a running development API and compare every prediction with Step 8."""
import argparse
import csv
import json
from pathlib import Path
import time
import httpx


def no_private_fields(value):
    if isinstance(value,dict):
        if {'weak_reference_arc','reference_route','reference_labels','labels'}&set(value):raise ValueError('Private reference fields in public response')
        for child in value.values():no_private_fields(child)
    elif isinstance(value,list):
        for child in value:no_private_fields(child)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url',default='http://127.0.0.1:8000')
    parser.add_argument('--expected',type=Path,default=Path('results/experiments/hmm_viterbi'))
    parser.add_argument('--report',type=Path,default=Path('results/experiments/api/verification.json'))
    args=parser.parse_args();comparison=list(csv.DictReader((args.expected/'comparison.csv').open()));reports=[]
    ids=sorted({r['trip_id'] for r in comparison})
    with httpx.Client(base_url=args.base_url,timeout=180) as client:
        health=client.get('/readyz');health.raise_for_status();health=health.json()
        if health['partition']!='student_test':raise ValueError('Development verifier refuses evaluator partition')
        trips=client.get('/trips');trips.raise_for_status()
        if trips.json()['trip_ids']!=ids or len(ids)!=10:raise ValueError('Expected ten student-development trips')
        assert client.post('/predict',json={'trip_id':'99999999'}).status_code==404
        assert client.post('/predict',json={'trip_id':'../route'}).status_code==422
        assert client.post('/predict',json={'trip_id':ids[0],'route':[0]}).status_code==422
        for trip_id in ids:
            start=time.perf_counter();response=client.post('/predict',json={'trip_id':trip_id});elapsed=time.perf_counter()-start
            response.raise_for_status();body=response.json();no_private_fields(body)
            assert response.headers['X-Request-ID']==body['request_id']
            expected=list(csv.DictReader((args.expected/f'{trip_id}_predictions.csv').open()))
            actual=body['prediction']['observations'];assert len(actual)==len(expected)==len(body['gps_observations'])
            for row,old in zip(actual,expected):
                assert row['observation_id']==int(old['observation_id'])
                for key,prior in [('classifier_arc_id','classifier_arc'),('predicted_arc_id','hmm_arc')]:
                    assert row[key]==(int(old[prior]) if old[prior] else None)
            evaluation=body['evaluation'];assert evaluation['status']=='ok'
            metrics=next(r for r in comparison if r['trip_id']==trip_id and r['method']=='hmm_viterbi')
            for public,recorded in [('hmm_weak_reference_top1','weak_reference_top1'),('reference_sequence_edit_similarity','reference_sequence_edit_similarity'),('reference_arc_set_f1','reference_arc_set_f1')]:
                assert abs(evaluation[public]-float(metrics[recorded]))<1e-12
            reports.append({'trip_id':trip_id,'http_status':response.status_code,'request_id':body['request_id'],'observations':len(actual),
                            'predictions_match_step8':True,'aggregate_scores_match_step8':True,'client_request_seconds':elapsed})
            print(f'{trip_id}: HTTP 200; {len(actual)} predictions and aggregate scores match',flush=True)
    report={'verification_mode':'live HTTP against uvicorn on loopback','bundle_version':health['bundle_version'],'partition':'student_test',
            'unknown_trip_status':404,'invalid_or_extra_input_status':422,'trips':reports,'total_observations':sum(r['observations'] for r in reports),
            'all_predictions_match':True,'all_aggregate_scores_match':True,'reference_arrays_exposed':False,'evaluator_inference_run':False}
    args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='trips'},indent=2))


if __name__=='__main__':main()
