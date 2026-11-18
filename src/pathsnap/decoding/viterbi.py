"""Candidate-state HMM/Viterbi with explicit sequence boundaries and no references."""
import numpy as np
from scipy.special import logsumexp


def prepare_sequence(observations,probabilities,track,network,config):
    if len(observations)!=len(probabilities) or len(track)!=len(observations):raise ValueError('Observation lengths differ')
    if not 0<config['emission_epsilon']<=1:raise ValueError('Invalid emission epsilon')
    xy=np.full((len(track),2),np.nan)
    valid=[i for i,row in enumerate(track) if row is not None and len(row)==3 and np.isfinite(row).all()]
    if valid:xy[valid]=network.project([track[i][:2] for i in valid])
    steps=[]
    for i,(row,probability) in enumerate(zip(observations,probabilities)):
        candidates=row['candidates'];p=np.asarray(probability,dtype=float)
        if p.shape!=(len(candidates),) or not np.isfinite(p).all() or np.any((p<0)|(p>1)):raise ValueError('Invalid candidate probabilities')
        if candidates and not np.isfinite(xy[i]).all():raise ValueError('Candidates for invalid GPS observation')
        ids=[c['arc_id'] for c in candidates]
        if len(ids)!=len(set(ids)) or any(a<0 or a>=len(network.arcs) for a in ids):raise ValueError('Invalid candidate IDs')
        if any(not 0<=c['projection_fraction']<=1 for c in candidates):raise ValueError('Invalid projection fraction')
        emission=np.log(np.maximum(p,config['emission_epsilon']))
        if len(emission):emission-=logsumexp(emission)
        reason=None;distances=None;displacement=0.0
        if not candidates:reason='no_candidates'
        elif i==0:reason='start'
        elif not observations[i-1]['candidates']:reason='after_missing_candidates'
        else:
            dt=track[i][2]-track[i-1][2]
            if not np.isfinite(dt) or dt<=0:reason='invalid_time'
            elif dt>config['gap_reset_s']:reason='gps_gap'
            else:
                displacement=float(np.linalg.norm(xy[i]-xy[i-1]))
                distances=network.distance_matrix(observations[i-1]['candidates'],candidates,config['backward_tolerance_m'])
                distances[distances>config['max_speed_m_s']*dt+config['transition_noise_m']]=np.inf
        steps.append(dict(ids=ids,emission=emission,distances=distances,displacement_m=displacement,reset_reason=reason))
    return steps


def decode(steps,beta_m):
    if not np.isfinite(beta_m) or beta_m<=0:raise ValueError('beta_m must be finite and positive')
    result=[None]*len(steps);history=[];pointers=[];delta=None;segment=0;reasons={}
    def finish():
        nonlocal history,pointers,delta,segment
        if not history:return
        state=int(np.argmax(delta))
        for k in range(len(history)-1,-1,-1):
            i=history[k]
            result[i]=dict(observation_id=i,predicted_arc=steps[i]['ids'][state],segment_id=segment,reset_reason=reasons.get(i))
            if k:state=int(pointers[k][state])
        segment+=1;history=[];pointers=[];delta=None
    for i,step in enumerate(steps):
        reason=step['reset_reason']
        if reason is not None:
            finish()
            if not step['ids']:
                result[i]=dict(observation_id=i,predicted_arc=None,segment_id=None,reset_reason=reason);continue
        if delta is None:
            reasons[i]=reason or 'restart';delta=step['emission']-np.log(len(step['ids']))
            history=[i];pointers=[None];continue
        distances=step['distances']
        raw=-np.abs(distances-step['displacement_m'])/beta_m
        valid_rows=np.isfinite(raw).any(axis=1)
        transition=np.full_like(raw,-np.inf)
        transition[valid_rows]=raw[valid_rows]-logsumexp(raw[valid_rows],axis=1,keepdims=True)
        scores=delta[:,None]+transition
        best=np.argmax(scores,axis=0);current=step['emission']+np.max(scores,axis=0)
        if not np.isfinite(current).any():
            finish();reasons[i]='no_valid_transition'
            delta=step['emission']-np.log(len(step['ids']));history=[i];pointers=[None]
        else:history.append(i);pointers.append(best);delta=current
    finish();return result


def selected_candidates(observations,predictions):
    return [next((c for c in row['candidates'] if c['arc_id']==prediction['predicted_arc']),None)
            for row,prediction in zip(observations,predictions)]


def reconstruct_route(observations,predictions,steps,network,config):
    """Expand valid state transitions; retain separate parts at missing/gap/invalid edges."""
    selected=selected_candidates(observations,predictions);parts=[];previous=None;part=[]
    for i,current in enumerate(selected):
        if current is None:
            if part:parts.append(part)
            part=[];previous=None;continue
        reset=(previous is None or steps[i]['reset_reason'] is not None or
               predictions[i].get('reset_reason')=='no_valid_transition')
        connector=None
        if not reset:
            before=observations[i-1]['candidates'];after=observations[i]['candidates']
            a=next(j for j,c in enumerate(before) if c['arc_id']==previous['arc_id'])
            b=next(j for j,c in enumerate(after) if c['arc_id']==current['arc_id'])
            if not np.isfinite(steps[i]['distances'][a,b]):reset=True
            elif previous['arc_id']==current['arc_id'] and (current['projection_fraction']-previous['projection_fraction'])*network.lengths[current['arc_id']]>=-config['backward_tolerance_m']:
                connector=[]
            else:connector=network.connector(network.arcs[previous['arc_id'],1],network.arcs[current['arc_id'],0])
        if reset or connector is None:
            if part:parts.append(part)
            part=[current['arc_id']]
        else:
            part.extend(connector)
            if connector or current['arc_id']!=previous['arc_id']:part.append(current['arc_id'])
        previous=current
    if part:parts.append(part)
    return parts
