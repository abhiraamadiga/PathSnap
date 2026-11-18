"""Reproducible EDA of development trips, with raw-data Folium maps."""
import argparse
import csv
import json
import math
from collections import Counter
from pathlib import Path

from pathsnap.data.loading import load_trips


def haversine(a, b):
    """Spherical distance in metres for (longitude, latitude) coordinates."""
    lon1, lat1, lon2, lat2 = map(math.radians, (*a[:2], *b[:2]))
    term = math.sin((lat2-lat1)/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2
    return 6371008.8 * 2 * math.asin(math.sqrt(min(1, max(0, term))))


def describe(values):
    import numpy as np
    array = np.asarray(values, dtype=float)
    return {name: float(value) for name, value in zip(
        ['min', 'p25', 'median', 'p75', 'p95', 'max', 'mean'],
        [*np.percentile(array, [0, 25, 50, 75, 95, 100]), np.mean(array)])} if len(array) else {}


def make_map(trip, destination):
    import folium
    gps, nodes, arcs = (trip.rows[k] for k in ['track', 'nodes', 'arcs'])
    swap = lambda row: [row[1], row[0]]
    m = folium.Map(location=swap(gps[0]), tiles='OpenStreetMap')
    # Every road arc is retained, using one GeoJSON layer rather than thousands of objects.
    geometry = {'type': 'Feature', 'properties': {}, 'geometry': {'type': 'MultiLineString',
                'coordinates': [[nodes[u], nodes[v]] for u, v in arcs]}}
    folium.GeoJson(geometry, name='Road network', style_function=lambda _: {'color': '#8293a3', 'weight': 1, 'opacity': .45}).add_to(m)
    reference = folium.FeatureGroup(name='Reference arcs (not GPS-aligned labels)')
    # Draw arcs separately: never fabricate straight connectors across reference breaks.
    for (arc_id,) in trip.rows['route']:
        u, v = arcs[arc_id]
        folium.PolyLine([swap(nodes[u]), swap(nodes[v])], color='#16803c', weight=5, opacity=.8).add_to(reference)
    reference.add_to(m)
    observations = folium.FeatureGroup(name='Raw GPS observations')
    for i, row in enumerate(gps):
        folium.CircleMarker(swap(row), radius=2, color='#2166d1', fill=True,
                            tooltip=f'GPS row {i}; time {row[2]} s').add_to(observations)
    observations.add_to(m)
    gaps = folium.FeatureGroup(name='Gap endpoints (>1 second)')
    for i, (a, b) in enumerate(zip(gps, gps[1:])):
        if b[2]-a[2] > 1:
            folium.CircleMarker(swap(b), radius=5, color='#d74916', tooltip=f'After gap {b[2]-a[2]:g} s; GPS row {i+1}').add_to(gaps)
    gaps.add_to(m)
    m.fit_bounds([[min(r[1] for r in gps), min(r[0] for r in gps)],
                  [max(r[1] for r in gps), max(r[0] for r in gps)]])
    folium.LayerControl().add_to(m)
    m.get_root().html.add_child(folium.Element('<div style="position:fixed;bottom:25px;left:25px;z-index:9999;background:white;padding:12px">'
        f'{trip.partition}/{trip.trip_id}<br>Blue: GPS; green: reference; grey: roads; orange: gap endpoints<br>No predictions yet; reference segments are drawn individually.</div>'))
    destination.write_text('\n'.join(line.rstrip() for line in m.get_root().render().splitlines()) + '\n')


def main():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--results', type=Path, default=Path('results'))
    args = parser.parse_args()
    out = args.results
    for sub in ['experiments/eda', 'figures', 'maps']:
        (out/sub).mkdir(parents=True, exist_ok=True)
    records, intervals = [], {'train': [], 'student_test': []}
    breaks = []
    selected = {('train', '00000090'), ('student_test', '00000007')}
    observed = Counter()
    for trip in load_trips(args.source):
        observed[trip.partition] += 1
        if trip.issues:
            raise ValueError(f'Validate malformed input before EDA: {trip.trip_id}')
        gps, nodes, arcs, route = (trip.rows[k] for k in ['track', 'nodes', 'arcs', 'route'])
        dt = [b[2]-a[2] for a, b in zip(gps, gps[1:])]
        distance = [haversine(a,b) for a,b in zip(gps,gps[1:])]
        intervals[trip.partition].extend(dt)
        speed = [d/t for d,t in zip(distance,dt) if t > 0]
        rec = dict(partition=trip.partition, trip_id=trip.trip_id, gps_points=len(gps), nodes=len(nodes), arcs=len(arcs),
                   reference_entries=len(route), elapsed_s=gps[-1][2]-gps[0][2],
                   observed_displacement_km=sum(distance)/1000, max_gap_s=max(dt), gaps_over_1s=sum(t>1 for t in dt),
                   duplicate_gps_rows=len(gps)-len(set(gps)), repeated_positions=len(gps)-len({r[:2] for r in gps}),
                   duplicate_node_positions=len(nodes)-len(set(nodes)), duplicate_arc_pairs=len(arcs)-len(set(arcs)),
                   self_loop_arcs=sum(u==v for u,v in arcs), max_observed_speed_m_s=max(speed),
                   missing_rows=sum(row is None for kind in trip.rows.values() for row in kind))
        records.append(rec)
        for i, (a,b) in enumerate(zip(route,route[1:])):
            u,v=arcs[a[0]]; x,y=arcs[b[0]]
            if v != x:
                breaks.append(dict(partition=trip.partition, trip_id=trip.trip_id, route_row=i,
                                   from_arc=a[0], to_arc=b[0], endpoint_distance_m=haversine(nodes[v],nodes[x]),
                                   repeated_arc=a==b))
        if (trip.partition,trip.trip_id) in selected:
            make_map(trip, out/'maps'/f'{trip.partition}_{trip.trip_id}.html')
    if observed != {'train':80, 'student_test':10}:
        raise ValueError(f'Unexpected development partitions: {observed}')
    for name, rows in [('trip_statistics', records), ('reference_breaks', breaks)]:
        with (out/'experiments/eda'/f'{name}.csv').open('w',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=rows[0].keys(),lineterminator='\n')
            writer.writeheader(); writer.writerows(rows)
    summary={p:{key:describe([r[key] for r in records if r['partition']==p]) for key in records[0] if key not in ['partition','trip_id']} for p in intervals}
    for p in intervals:
        summary[p]['sampling_interval_s']=describe(intervals[p])
    (out/'experiments/eda/summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    fig,axes=plt.subplots(2,2,figsize=(11,8),layout='constrained')
    for ax,key,label in zip(axes.flat,['gps_points','elapsed_s','arcs','observed_displacement_km'],
                           ['GPS observations per trip','Elapsed duration (seconds)','Road arcs per trip','Sum of GPS displacements (km)']):
        values=[[r[key] for r in records if r['partition']==p] for p in intervals]
        ax.boxplot(values, tick_labels=list(intervals)); ax.set_title(label); ax.set_yscale('log'); ax.grid(axis='y',alpha=.25)
    fig.suptitle('Development partitions: per-trip distributions (log scales)')
    fig.savefig(out/'figures/trip_distributions.png',dpi=160); plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(11,4),layout='constrained')
    for p,values in intervals.items():
        counts=[sum(t==1 for t in values),sum(1<t<=5 for t in values),sum(5<t<=60 for t in values),sum(t>60 for t in values)]
        axes[0].plot(['1 s','(1,5] s','(5,60] s','>60 s'],[100*c/len(values) for c in counts],marker='o',label=p)
        subset=[r for r in records if r['partition']==p]
        axes[1].scatter([r['gps_points'] for r in subset],[r['arcs'] for r in subset],label=p,alpha=.7)
    axes[0].set(title='Sampling interval buckets',ylabel='Percentage of adjacent observations'); axes[0].legend()
    axes[1].set(title='GPS count versus network size',xlabel='GPS observations',ylabel='Road arcs'); axes[1].legend()
    fig.savefig(out/'figures/sampling_and_network.png',dpi=160); plt.close(fig)
    print(json.dumps({'partitions':dict(observed),'reference_breaks':len(breaks),'maps':sorted(str(p) for p in (out/'maps').glob('*.html'))},indent=2))


if __name__ == '__main__':
    main()
