"""Load candidate data with trip IDs retained for grouped validation."""
from dataclasses import dataclass
import gzip
import itertools
import json
from pathlib import Path
import numpy as np
from pathsnap.features.preprocessing import FEATURES


@dataclass
class Dataset:
    X: np.ndarray
    y: np.ndarray
    groups: np.ndarray
    observations: list
    coverage: list


def load_dataset(root, partition, limit=None, seed=42):
    """Training samples whole eligible observations, retaining every candidate.

    Evaluation includes all observations, including abstentions and candidate misses.
    Labels are never included in X. Only training is capped; limit=None means full.
    """
    if partition not in ('train','student_test'):raise ValueError('Development partitions only')
    if limit is not None and (not isinstance(limit,int) or limit<1):raise ValueError('Invalid observation cap')
    rng=np.random.default_rng(seed)
    X=[];y=[];groups=[];observations=[];coverage=[]
    for folder in sorted((Path(root)/partition).iterdir()):
        if not folder.is_dir():continue
        eligible=[];counts=dict(trip_id=folder.name,observations=0,accepted_labels=0,candidate_misses=0,no_candidates=0,used_observations=0)
        with gzip.open(folder/'observations.jsonl.gz','rt') as obs, gzip.open(folder/'weak_labels.jsonl.gz','rt') as labels:
            for a,b in itertools.zip_longest(obs,labels):
                if a is None or b is None:raise ValueError('Mismatched observation/label counts')
                row,label=json.loads(a),json.loads(b)
                if row['observation_id']!=counts['observations'] or label['observation_id']!=row['observation_id']:raise ValueError('Misaligned observation IDs')
                counts['observations']+=1
                candidates=row['candidates'];reference=label['arc_id']
                present=reference in {c['arc_id'] for c in candidates} if reference is not None else False
                counts['accepted_labels']+=reference is not None
                counts['candidate_misses']+=reference is not None and not present
                counts['no_candidates']+=not candidates
                if partition=='student_test' or (reference is not None and present):
                    eligible.append((row,reference))
        if partition=='train' and limit is not None and len(eligible)>limit:
            selected=np.sort(rng.choice(len(eligible),limit,replace=False));eligible=[eligible[i] for i in selected]
        counts['used_observations']=len(eligible);coverage.append(counts)
        for row,reference in eligible:
            begin=len(X)
            for c in row['candidates']:
                values=[c[key] for key in FEATURES]
                if not np.isfinite(values).all():raise ValueError('Nonfinite feature value')
                X.append(values);y.append(int(c['arc_id']==reference));groups.append(folder.name)
            observations.append(dict(trip_id=folder.name,observation_id=row['observation_id'],reference=reference,
                                     begin=begin,end=len(X),arc_ids=[c['arc_id'] for c in row['candidates']],
                                     gap_reset=bool(row['candidates'][0]['gap_reset']) if row['candidates'] else True))
    if not X:raise ValueError(f'No candidate rows in {partition}')
    return Dataset(np.asarray(X,dtype=float),np.asarray(y,dtype=int),np.asarray(groups),observations,coverage)
