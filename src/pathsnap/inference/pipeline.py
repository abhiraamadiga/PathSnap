"""Inference accepts GPS/nodes/arcs only; no reference or scoring inputs."""
import math
import time
import numpy as np
from threadpoolctl import threadpool_limits
from pathsnap.features.candidates import prepare,FEATURES
from pathsnap.decoding.network import RoadNetwork
from pathsnap.decoding.viterbi import prepare_sequence,decode,reconstruct_route


def validate_geometry(nodes,arcs):
    nodes=np.asarray(nodes,dtype=float);arcs=np.asarray(arcs,dtype=float)
    if nodes.ndim!=2 or nodes.shape[1]!=2 or not len(nodes) or not np.isfinite(nodes).all():raise ValueError('Nodes require finite longitude/latitude pairs')
    if np.any(np.abs(nodes[:,0])>180) or np.any(np.abs(nodes[:,1])>90):raise ValueError('Node coordinates out of range')
    if arcs.ndim!=2 or arcs.shape[1]!=2 or not len(arcs) or not np.isfinite(arcs).all() or np.any(arcs!=np.floor(arcs)):
        raise ValueError('Arcs require integer node IDs')
    if arcs.min()<0 or arcs.max()>=len(nodes):raise ValueError('Arc references missing node')
    return nodes.tolist(),arcs.astype(int).tolist()


def normalise_track(track):
    rows=[]
    for row in track:
        try:
            if isinstance(row,(str,bytes)):raise ValueError('GPS row must be a sequence')
            values=tuple(float(v) for v in row)
            valid=len(values)==3 and all(math.isfinite(v) for v in values) and -180<=values[0]<=180 and -90<=values[1]<=90
        except (TypeError,ValueError):valid=False
        rows.append(values if valid else None)
    return rows


class Predictor:
    def __init__(self,model,preprocessing,hmm,model_config,manifest):
        self.model=model;self.preprocessing=preprocessing;self.hmm=hmm;self.model_config=model_config;self.manifest=manifest

    def predict(self,track,nodes,arcs):
        start=time.perf_counter();nodes,arcs=validate_geometry(nodes,arcs);track=normalise_track(track)
        if not track:raise ValueError('Track must contain at least one observation')
        _,observations=prepare(track,nodes,arcs,self.preprocessing)
        X=np.asarray([[c[key] for key in FEATURES] for row in observations for c in row['candidates']],dtype=float).reshape(-1,len(FEATURES))
        if not np.isfinite(X).all():raise ValueError('Nonfinite inference features')
        with threadpool_limits(limits=self.model_config['model_parameters']['n_jobs']):
            probability=self.model.predict_proba(X)[:,list(self.model.classes_).index(self.model_config['positive_class'])] if len(X) else np.array([])
        per_observation=[];offset=0;classifier=[]
        for row in observations:
            n=len(row['candidates']);scores=probability[offset:offset+n];offset+=n;per_observation.append(scores)
            classifier.append(row['candidates'][int(np.argmax(scores))]['arc_id'] if n else None)
        network=RoadNetwork(nodes,arcs,self.hmm['max_route_distance_m'],self.hmm['routing_cache_sources'])
        steps=prepare_sequence(observations,per_observation,track,network,self.hmm)
        decoded=decode(steps,self.hmm['beta_m']);parts=reconstruct_route(observations,decoded,steps,network,self.hmm)
        output=[]
        for row,prediction,raw in zip(observations,decoded,classifier):
            output.append(dict(observation_id=row['observation_id'],status=row['status'],candidate_count=len(row['candidates']),
                               classifier_arc_id=raw,predicted_arc_id=prediction['predicted_arc'],segment_id=prediction['segment_id'],reset_reason=prediction['reset_reason']))
        geometries=[dict(arc_ids=part,geometry={'type':'MultiLineString','coordinates':[[nodes[arcs[a][0]],nodes[arcs[a][1]]] for a in part]}) for part in parts]
        return dict(schema_version=1,bundle_version=self.manifest['bundle_version'],observations=output,route_parts=geometries,
                    diagnostics={'observation_count':len(track),'candidate_rows':len(X),'invalid_observations':sum(r['status']=='invalid_observation' for r in observations),
                                 'no_candidate_observations':sum(not r['candidates'] for r in observations),'route_parts':len(parts),
                                 'no_valid_transition_resets':sum(p['reset_reason']=='no_valid_transition' for p in decoded)},
                    prediction_seconds=time.perf_counter()-start)
