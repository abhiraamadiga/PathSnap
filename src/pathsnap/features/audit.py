"""Audit generated feature files before fitting any model or scaler."""
import argparse
import csv
import gzip
import itertools
import json
import math
from pathlib import Path
from pathsnap.features.preprocessing import FEATURES


def audit_trip(folder):
    counts=dict(observations=0,candidate_rows=0,no_candidates=0,accepted_weak_labels=0,
                usable_observations=0,weak_label_candidate_misses=0,invalid_feature_values=0)
    stats={key:[0,0.0,0.0,math.inf,-math.inf] for key in FEATURES}
    with gzip.open(folder/'observations.jsonl.gz','rt') as observations, gzip.open(folder/'weak_labels.jsonl.gz','rt') as labels:
        for observation,label in itertools.zip_longest(observations,labels):
            if observation is None or label is None: raise ValueError('Observation/label count mismatch')
            row,target=json.loads(observation),json.loads(label)
            if row['observation_id']!=counts['observations'] or target['observation_id']!=row['observation_id']:
                raise ValueError('Observation IDs out of order or misaligned')
            if set(row)!= {'observation_id','status','candidates'}: raise ValueError('Unexpected observation fields')
            candidates=row['candidates']; ids=[c['arc_id'] for c in candidates]
            if len(ids)!=len(set(ids)): raise ValueError('Duplicate candidate arc IDs')
            counts['observations']+=1;counts['candidate_rows']+=len(candidates)
            counts['no_candidates']+=not candidates
            accepted=target['arc_id'] is not None
            counts['accepted_weak_labels']+=accepted
            counts['usable_observations']+=accepted and target['arc_id'] in ids
            counts['weak_label_candidate_misses']+=accepted and target['arc_id'] not in ids
            for candidate in candidates:
                if set(candidate)!=set(FEATURES)|{'arc_id'}: raise ValueError('Feature schema mismatch / unexpected label field')
                for key in FEATURES:
                    value=candidate[key]
                    if not isinstance(value,(int,float)) or not math.isfinite(value):
                        counts['invalid_feature_values']+=1;continue
                    # Welford moments avoid subtracting two nearly equal sums.
                    stat=stats[key];stat[0]+=1
                    delta=value-stat[1];stat[1]+=delta/stat[0];stat[2]+=delta*(value-stat[1])
                    stat[3]=min(stat[3],value);stat[4]=max(stat[4],value)
    return counts,stats


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=Path('data/processed/step4'))
    parser.add_argument('--output',type=Path,default=Path('results/experiments/feature_audit'))
    args=parser.parse_args()
    trips=[];features=[]
    for partition in ['train','student_test']:
        for folder in sorted((args.source/partition).glob('*')):
            if not folder.is_dir():continue
            counts,stats=audit_trip(folder)
            trips.append(dict(partition=partition,trip_id=folder.name,**counts))
            for key,(n,mean,m2,minimum,maximum) in stats.items():
                features.append(dict(partition=partition,trip_id=folder.name,feature=key,count=n,
                                     mean=mean if n else None,std=math.sqrt(max(0,m2/n)) if n else None,
                                     minimum=minimum if n else None,maximum=maximum if n else None))
    if not trips:raise SystemExit('No processed trip files: run pathsnap.features.build first')
    args.output.mkdir(parents=True,exist_ok=True)
    for name,rows in [('trip_audit',trips),('feature_statistics',features)]:
        with (args.output/f'{name}.csv').open('w',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=rows[0],lineterminator='\n');writer.writeheader();writer.writerows(rows)
    summary={'feature_columns':FEATURES,'labels':'weak geometric reference labels, not verified GPS truth',
             'partitions':{p:{'trips':sum(r['partition']==p for r in trips),
                              **{key:sum(r[key] for r in trips if r['partition']==p) for key in counts}}
                           for p in ['train','student_test']},
             'no_usable_label_trips':[f"{r['partition']}/{r['trip_id']}" for r in trips if not r['usable_observations']]}
    (args.output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))
    if any(r['invalid_feature_values'] for r in trips):raise SystemExit('Nonfinite/invalid feature values found')


if __name__=='__main__':main()
