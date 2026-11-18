"""Development-only weak reference alignment; excluded from inference bundles."""
import math
import numpy as np

def align_reference(track, index, route, radius_m=75.0, margin_m=5.0):
    """Weak development labels: nearest reference arc with distance/margin abstention.

    This is NOT verified observation ground truth. It does not enforce reference
    chronology or infer travel direction. Repeated occurrences of the same arc are
    collapsed only for geometric lookup; original road IDs are never renumbered.
    """
    ids = np.unique([row[0] for row in route])
    if len(ids) and (ids.min()<0 or ids.max()>=len(index.length)):
        raise ValueError('Invalid reference arc ID')
    labels=[]
    for raw in track:
        if raw is None or not all(math.isfinite(v) for v in raw) or not -180<=raw[0]<=180 or not -90<=raw[1]<=90:
            labels.append({'arc_id':None,'reason':'invalid_observation'}); continue
        if not len(ids):
            labels.append({'arc_id':None,'reason':'empty_reference'}); continue
        point=index.project([raw[:2]])[0]
        distances,_=index.distances(point,ids)
        order=np.lexsort((ids,distances)); best=order[0]
        distance=float(distances[best])
        margin=float(distances[order[1]]-distance) if len(order)>1 else None
        reason='accepted_weak_label'
        if distance>radius_m: reason='reference_too_far'
        elif margin is not None and margin<margin_m: reason='ambiguous_reference'
        labels.append({'arc_id':int(ids[best]) if reason=='accepted_weak_label' else None,
                       'reason':reason,'distance_m':distance,'margin_m':margin})
    return labels
