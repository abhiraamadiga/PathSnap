"""Development-only pointwise and reference-sequence diagnostics."""


def edit_similarity(a,b):
    if not a and not b:return 1.0
    if len(a)>len(b):a,b=b,a
    previous=list(range(len(a)+1))
    for i,right in enumerate(b,1):
        current=[i]
        for j,left in enumerate(a,1):current.append(min(current[-1]+1,previous[j]+1,previous[j-1]+(left!=right)))
        previous=current
    return 1-previous[-1]/max(len(a),len(b))


def route_metrics(predictions,labels,parts,reference_route,steps,network):
    accepted=[i for i,label in enumerate(labels) if label['arc_id'] is not None]
    correct=sum(predictions[i]['predicted_arc']==labels[i]['arc_id'] for i in accepted)
    pairs=joined=0
    for i in range(1,len(predictions)):
        a=predictions[i-1]['predicted_arc'];b=predictions[i]['predicted_arc']
        if a is not None and b is not None and steps[i]['reset_reason'] is None:
            pairs+=1;joined+=a==b or network.arcs[a,1]==network.arcs[b,0]
    flat=[arc for part in parts for arc in part];reference=[r[0] for r in reference_route]
    predicted_set=set(flat);reference_set=set(reference);shared=len(predicted_set&reference_set)
    precision=shared/len(predicted_set) if predicted_set else 0
    recall=shared/len(reference_set) if reference_set else 0
    continuity_checks=sum(len(part)-1 for part in parts)
    connected=sum(network.arcs[a,1]==network.arcs[b,0] for part in parts for a,b in zip(part,part[1:]))
    if connected!=continuity_checks:raise ValueError('Reconstructed route contains a disconnected part')
    return dict(observations=len(predictions),accepted_weak_labels=len(accepted),correct_weak_labels=int(correct),
                weak_reference_top1=correct/len(accepted) if accepted else None,
                temporal_pairs=pairs,directly_joined_pairs=int(joined),direct_continuity=joined/pairs if pairs else None,
                route_parts=len(parts),expanded_arc_entries=len(flat),reference_arc_entries=len(reference),
                reference_arc_set_precision=precision,reference_arc_set_recall=recall,
                reference_arc_set_f1=2*precision*recall/(precision+recall) if precision+recall else 0,
                reference_sequence_edit_similarity=edit_similarity(flat,reference),
                no_candidate_observations=sum(p['predicted_arc'] is None for p in predictions),
                decoder_unreachable_resets=sum(p.get('reset_reason')=='no_valid_transition' for p in predictions))
