"""Build local candidate datasets and separately stored weak development labels."""
import argparse
import csv
import gzip
import json
from collections import Counter
from pathlib import Path
from pathsnap.data.loading import load_trips
from pathsnap.data.validation import validate_trip
from pathsnap.features.preprocessing import prepare, align_reference, FEATURES


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--config',type=Path,default=Path('configs/preprocessing.json'))
    parser.add_argument('--output',type=Path,default=Path('data/processed/step4'))
    parser.add_argument('--summary',type=Path,default=Path('results/experiments/preprocessing'))
    parser.add_argument('--trip',action='append',help='Optional trip ID filter for smoke checks')
    args=parser.parse_args()
    config=json.loads(args.config.read_text())
    for key in ['candidate_radius_m','sample_spacing_m','gap_reset_s','reference_radius_m','reference_margin_m']:
        if config[key]<=0: raise ValueError(f'{key} must be positive')
    if not isinstance(config['max_candidates'],int) or config['max_candidates']<1: raise ValueError('Invalid max_candidates')
    summaries=[]
    for trip in load_trips(args.source):
        if args.trip and trip.trip_id not in args.trip: continue
        validation=validate_trip(trip)
        fatal=[k for k in validation['issues'] if k not in ['gaps over one second','nonjoining consecutive reference arcs','nonincreasing timestamps']]
        if fatal: raise ValueError(f'{trip.trip_id}: resolve data issues first: {fatal}')
        # Only track/nodes/arcs cross the feature boundary. Reference labels are separate.
        index,records=prepare(trip.rows['track'],trip.rows['nodes'],trip.rows['arcs'],config)
        labels=align_reference(trip.rows['track'],index,trip.rows['route'],config['reference_radius_m'],config['reference_margin_m'])
        destination=args.output/trip.partition/trip.trip_id
        destination.mkdir(parents=True,exist_ok=True)
        for filename,rows in [('observations',records),('weak_labels',labels)]:
            with gzip.open(destination/f'{filename}.jsonl.gz','wt',encoding='utf-8') as stream:
                for i,row in enumerate(rows):
                    if filename=='weak_labels': row={'observation_id':i,**row}
                    stream.write(json.dumps(row,allow_nan=False)+'\n')
        reasons=Counter(label['reason'] for label in labels)
        labeled=sum(label['arc_id'] is not None for label in labels)
        misses=sum(label['arc_id'] is not None and label['arc_id'] not in {c['arc_id'] for c in record['candidates']}
                   for label,record in zip(labels,records))
        summaries.append(dict(partition=trip.partition,trip_id=trip.trip_id,observations=len(records),
                              candidate_rows=sum(len(r['candidates']) for r in records),
                              no_candidates=sum(not r['candidates'] for r in records),
                              accepted_weak_labels=labeled,weak_label_candidate_misses=misses,
                              ambiguous_reference=reasons['ambiguous_reference'],reference_too_far=reasons['reference_too_far']))
        print(f"{trip.partition}/{trip.trip_id}: {labeled}/{len(records)} weak labels; {misses} candidate misses",flush=True)
    if not summaries: raise SystemExit('No matching trips')
    args.summary.mkdir(parents=True,exist_ok=True)
    with (args.summary/'trip_summary.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=summaries[0],lineterminator='\n');writer.writeheader();writer.writerows(summaries)
    totals={p:{k:sum(r[k] for r in summaries if r['partition']==p) for k in summaries[0] if k not in ['partition','trip_id']} for p in ['train','student_test']}
    report={'config':config,'features':FEATURES,'label_method':'nearest reference arc with abstention; weak labels, not verified ground truth',
            'trip_counts':dict(Counter(r['partition'] for r in summaries)), 'totals':totals}
    (args.summary/'summary.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__': main()
