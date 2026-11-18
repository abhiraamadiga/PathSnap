"""Actual GPS/reference/classifier/decoded road layers without fabricated bridges."""
from pathlib import Path
import folium


def route_map(trip,classifier_parts,hmm_parts,path):
    nodes=trip.rows['nodes'];arcs=trip.rows['arcs'];gps=trip.rows['track']
    m=folium.Map(location=[gps[0][1],gps[0][0]],tiles='OpenStreetMap')
    def layer(name,ids,color,weight,opacity=.8):
        coordinates=[[nodes[arcs[a][0]],nodes[arcs[a][1]]] for a in ids]
        geometry={'type':'Feature','properties':{},'geometry':{'type':'MultiLineString','coordinates':coordinates}}
        folium.GeoJson(geometry,name=name,style_function=lambda _,c=color,w=weight,o=opacity:{'color':c,'weight':w,'opacity':o}).add_to(m)
    layer('Road network',range(len(arcs)),'#8b9baa',1,.35)
    layer('Reference route (development only)',[r[0] for r in trip.rows['route']],'#16803c',6)
    layer('Classifier route parts',[a for part in classifier_parts for a in part],'#e07b1a',4)
    layer('HMM/Viterbi route parts',[a for part in hmm_parts for a in part],'#7b2cbf',3)
    observations=folium.FeatureGroup(name='Raw GPS observations')
    for i,row in enumerate(gps):
        folium.CircleMarker([row[1],row[0]],radius=2,color='#2166d1',fill=True,tooltip=f'GPS row {i}; time {row[2]} s').add_to(observations)
    observations.add_to(m);folium.LayerControl().add_to(m)
    m.fit_bounds([[min(r[1] for r in gps),min(r[0] for r in gps)],[max(r[1] for r in gps),max(r[0] for r in gps)]])
    m.get_root().html.add_child(folium.Element('<div style="position:fixed;bottom:25px;left:25px;z-index:9999;background:white;padding:10px">'
        f'{trip.partition}/{trip.trip_id}<br>Blue: GPS; green: reference; orange: classifier; purple: HMM<br>Parts are drawn as road arcs; no lines bridge a reset.</div>'))
    Path(path).write_text('\n'.join(line.rstrip() for line in m.get_root().render().splitlines())+'\n')
