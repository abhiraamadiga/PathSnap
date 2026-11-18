"""Generate phase-one coverage figures and targeted diagnostic maps."""
import argparse
import csv
import json
from pathlib import Path
from pathsnap.data.loading import load_trips
from pathsnap.visualization.eda import make_map


def main():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True,help='Original development ZIP or extracted directory')
    parser.add_argument('--audit',type=Path,default=Path('results/experiments/feature_audit'))
    parser.add_argument('--output',type=Path,default=Path('results/phase1'))
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    summary=json.loads((args.audit/'summary.json').read_text())
    rows=list(csv.DictReader((args.audit/'trip_audit.csv').open()))
    fig,axes=plt.subplots(1,2,figsize=(12,5),layout='constrained')
    worst=sorted(rows,key=lambda r:int(r['no_candidates'])/int(r['observations']),reverse=True)[:6]
    axes[0].barh([r['partition']+'/'+r['trip_id'] for r in reversed(worst)],
                 [100*int(r['no_candidates'])/int(r['observations']) for r in reversed(worst)],color='#cc6b35')
    axes[0].set(title='Largest no-candidate rates (75 m baseline)',xlabel='Observations with no candidate (%)',xlim=(0,100))
    bottom=[0,0];partitions=list(summary['partitions'])
    for key,title,color in [('usable_observations','Usable weak label','#287c66'),('weak_label_candidate_misses','Accepted label absent from top-8','#d88620')]:
        values=[100*summary['partitions'][p][key]/summary['partitions'][p]['observations'] for p in partitions]
        axes[1].bar(partitions,values,bottom=bottom,label=title,color=color);bottom=[a+b for a,b in zip(bottom,values)]
    axes[1].bar(partitions,[100-b for b in bottom],bottom=bottom,label='Unlabelled / abstained',color='#9aaabd')
    axes[1].set(title='Weak-label availability, not accuracy',ylabel='Observations (%)',ylim=(0,100));axes[1].legend(loc='upper center',bbox_to_anchor=(.5,-.08))
    fig.savefig(args.output/'coverage.png',dpi=160);plt.close(fig)
    selected={'00000054','00000011'};cases=[]
    for trip in load_trips(args.source):
        if trip.partition!='train' or trip.trip_id not in selected:continue
        nodes=trip.rows['nodes'];gps=trip.rows['track']
        bounds=[min(n[0] for n in nodes),min(n[1] for n in nodes),max(n[0] for n in nodes),max(n[1] for n in nodes)]
        outside=sum(not(bounds[0]<=g[0]<=bounds[2] and bounds[1]<=g[1]<=bounds[3]) for g in gps)
        cases.append(dict(partition=trip.partition,trip_id=trip.trip_id,network_bounds_lon_lat=bounds,
                          gps_outside_network_bbox=outside,observations=len(gps),
                          note='Bounding box is a coarse geometry diagnostic, not a road-distance or label-validity test.'))
        make_map(trip,args.output/f'train_{trip.trip_id}.html')
        selected.remove(trip.trip_id)
        if not selected:break
    if selected:raise ValueError(f'Missing diagnostic trips: {selected}')
    (args.output/'case_diagnostics.json').write_text(json.dumps(cases,indent=2)+'\n')
    print(json.dumps(cases,indent=2))


if __name__=='__main__':main()
