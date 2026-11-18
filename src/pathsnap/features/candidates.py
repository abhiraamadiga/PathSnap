"""Label-free candidate features shared by training and inference."""
import math
import numpy as np
from pathsnap.features.spatial import RoadIndex

FEATURES = ['distance_m', 'projection_fraction', 'arc_length_m', 'heading_difference_rad',
            'heading_available', 'speed_m_s', 'dt_s', 'previous_distance_m', 'candidate_rank', 'gap_reset']


def prepare(track, nodes, arcs, config):
    """Accepts no reference labels. Returns one candidate list per observation.

    Invalid observations are retained with zero candidates. Large gaps reset motion
    features; data are neither imputed nor deduplicated. Row-based arc IDs survive.
    """
    index = RoadIndex(nodes, arcs, config['sample_spacing_m'])
    records = []
    previous = None
    for row_id, raw in enumerate(track):
        valid = (raw is not None and len(raw)==3 and all(math.isfinite(v) for v in raw)
                 and -180 <= raw[0] <= 180 and -90 <= raw[1] <= 90)
        if not valid:
            records.append({'observation_id':row_id, 'status':'invalid_observation', 'candidates':[]})
            previous = None
            continue
        point = index.project([raw[:2]])[0]
        dt = raw[2]-previous[1] if previous is not None else 0.0
        reset = previous is None or dt <= 0 or dt > config['gap_reset_s']
        move = np.zeros(2) if reset else point-previous[0]
        norm = float(np.linalg.norm(move))
        heading_available = not reset and norm > 1.0
        candidates = []
        for rank,(arc_id,distance,fraction) in enumerate(index.candidates(point, config['candidate_radius_m'], config['max_candidates']),1):
            length = float(index.length[arc_id])
            heading = 0.0
            usable_heading = heading_available and length > 0
            if usable_heading:
                cosine = float(np.dot(move,index.vector[arc_id])/(norm*length))
                heading = math.acos(max(-1.0,min(1.0,cosine)))
            prev_distance = distance if reset else float(index.distances(previous[0],[arc_id])[0][0])
            candidates.append({'arc_id':arc_id, 'distance_m':distance,'projection_fraction':fraction,
                               'arc_length_m':length,'heading_difference_rad':heading,
                               'heading_available':int(usable_heading),'speed_m_s':norm/dt if not reset else 0.0,
                               'dt_s':dt if dt>0 else 0.0,'previous_distance_m':prev_distance,
                               'candidate_rank':rank,'gap_reset':int(reset)})
        records.append({'observation_id':row_id,'status':'ok' if candidates else 'no_candidates','candidates':candidates})
        previous = (point,raw[2])
    return index,records
