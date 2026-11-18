"""Select decoder beta on five development trips; review on the other five."""
import argparse
import gzip
import json
from pathlib import Path
import time
import joblib
import numpy as np
from threadpoolctl import threadpool_limits
from pathsnap.data.loading import load_trips
from pathsnap.models.experiments import sha256,write_csv
from pathsnap.decoding.network import RoadNetwork
from pathsnap.decoding.viterbi import prepare_sequence,decode,reconstruct_route
from pathsnap.decoding.metrics import route_metrics
from pathsnap.visualization.decoding import route_map


def read_jsonl(path):
    with gzip.open(path,'rt') as stream:return [json.loads(line) for line in stream]


def load_context(trip,folder,model,model_config,config):
    # Features cross the inference boundary; weak labels are read separately for scoring.
    observations=read_jsonl(folder/'observations.jsonl.gz')
    if [r['observation_id'] for r in observations]!=list(range(len(trip.rows['track']))):raise ValueError('Observation order mismatch')
    X=np.asarray([[c[f] for f in model_config['feature_columns']] for r in observations for c in r['candidates']],dtype=float)
    if not np.isfinite(X).all():raise ValueError('Invalid features')
    start=time.perf_counter();probability=model.predict_proba(X)[:,list(model.classes_).index(1)] if len(X) else np.array([])
    inference=time.perf_counter()-start
    probabilities=[];offset=0
    for row in observations:
        n=len(row['candidates']);probabilities.append(probability[offset:offset+n]);offset+=n
    network=RoadNetwork(trip.rows['nodes'],trip.rows['arcs'],config['max_route_distance_m'],config['routing_cache_sources'])
    start=time.perf_counter();steps=prepare_sequence(observations,probabilities,trip.rows['track'],network,config);transition_time=time.perf_counter()-start
    classifier=[dict(observation_id=i,predicted_arc=row['candidates'][int(np.argmax(p))]['arc_id'] if len(p) else None,reset_reason=None)
                for i,(row,p) in enumerate(zip(observations,probabilities))]
    parts=reconstruct_route(observations,classifier,steps,network,config)
    labels=read_jsonl(folder/'weak_labels.jsonl.gz')
    if len(labels)!=len(observations) or [r['observation_id'] for r in labels]!=list(range(len(labels))):raise ValueError('Label ordering mismatch')
    metrics=route_metrics(classifier,labels,parts,trip.rows['route'],steps,network)
    return dict(trip=trip,observations=observations,network=network,steps=steps,labels=labels,
                classifier=classifier,classifier_parts=parts,classifier_metrics=metrics,
                classifier_seconds=inference,transition_seconds=transition_time)


def run_decoder(context,beta,config):
    start=time.perf_counter();predictions=decode(context['steps'],beta);decode_time=time.perf_counter()-start
    parts=reconstruct_route(context['observations'],predictions,context['steps'],context['network'],config)
    metrics=route_metrics(predictions,context['labels'],parts,context['trip'].rows['route'],context['steps'],context['network'])
    return dict(predictions=predictions,parts=parts,metrics=metrics,decode_seconds=decode_time)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True,help='Original development ZIP only')
    parser.add_argument('--data',type=Path,default=Path('data/processed/step4'))
    parser.add_argument('--model',type=Path,default=Path('artifacts/bayesian_optimization/tuned.joblib'))
    parser.add_argument('--config',type=Path,default=Path('configs/hmm_search.json'))
    parser.add_argument('--output',type=Path,default=Path('results/experiments/hmm_viterbi'))
    parser.add_argument('--maps',type=Path,default=Path('results/maps/hmm_viterbi'))
    args=parser.parse_args();config=json.loads(args.config.read_text());model_config=json.loads(Path('configs/tuned_model.json').read_text())
    baseline=json.loads(Path('results/experiments/model_comparison/manifest.json').read_text())
    if not args.source.is_file() or sha256(args.source)!=baseline['raw_source_sha256']:raise ValueError('Original development ZIP required; evaluator archive excluded')
    hashes={str(p.relative_to(args.data)):sha256(p) for p in sorted(args.data.glob('*/*/*.jsonl.gz'))}
    if hashes!=baseline['input_sha256']:raise ValueError('Feature inputs differ from baseline')
    selection_ids=set(config['selection_student_trip_ids']);review_ids=set(config['review_student_trip_ids'])
    if selection_ids&review_ids or len(selection_ids)!=5 or len(review_ids)!=5:raise ValueError('Require disjoint five-trip subsets')
    if not config['beta_candidates_m'] or any(not np.isfinite(b) or b<=0 for b in config['beta_candidates_m']):raise ValueError('Positive beta candidates required')
    for key in ['gap_reset_s','max_speed_m_s','max_route_distance_m']:
        if not np.isfinite(config[key]) or config[key]<=0:raise ValueError(f'Invalid {key}')
    for key in ['transition_noise_m','backward_tolerance_m']:
        if not np.isfinite(config[key]) or config[key]<0:raise ValueError(f'Invalid {key}')
    model=joblib.load(args.model)
    for key,value in model_config['model_parameters'].items():
        if model.get_params()[key]!=value:raise ValueError('Model/config mismatch')
    trips={}
    for trip in load_trips(args.source):
        if trip.partition=='student_test':trips[trip.trip_id]=trip
        if len(trips)==10:break
    if set(trips)!=selection_ids|review_ids:raise ValueError('Student-trip registry mismatch')
    args.output.mkdir(parents=True,exist_ok=True);args.maps.mkdir(parents=True,exist_ok=True)
    manifest={'config':config,'model_sha256':sha256(args.model),'model_config':model_config,'raw_development_sha256':sha256(args.source),
              'input_sha256':hashes,'policy':'Beta selected on first five declared student-development trips; other five only reviewed after selection. Neither subset is a fresh model test. No evaluator data used.'}
    (args.output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    contexts={};search=[];candidates={}
    with threadpool_limits(limits=4):
        for trip_id in sorted(selection_ids):
            print('Decoder selection trip '+trip_id,flush=True)
            context=load_context(trips[trip_id],args.data/'student_test'/trip_id,model,model_config,config);contexts[trip_id]=context
            for beta in config['beta_candidates_m']:
                result=run_decoder(context,beta,config);candidates[(trip_id,beta)]=result
                search.append(dict(trip_id=trip_id,beta_m=beta,**result['metrics'],decode_seconds=result['decode_seconds']))
            write_csv(args.output/'decoder_search.csv',search)
        means={beta:float(np.mean([r['weak_reference_top1'] for r in search if r['beta_m']==beta])) for beta in config['beta_candidates_m']}
        # Tie order is the predeclared beta list. Review-trip scores cannot affect it.
        best=max(config['beta_candidates_m'],key=lambda b:means[b])
        frozen={**config,'beta_m':best,'selection_means':means,'stage':'development_selected_hmm','classifier_config':'configs/tuned_model.json'}
        Path('configs/hmm.json').write_text(json.dumps(frozen,indent=2)+'\n')
        (args.output/'selection.json').write_text(json.dumps({'selected_beta_m':best,'selection_means':means,'selection_trip_ids':sorted(selection_ids),'review_trip_ids':sorted(review_ids)},indent=2)+'\n')
        results=[]
        for trip_id in sorted(trips):
            subset='selection' if trip_id in selection_ids else 'review'
            if trip_id not in contexts:
                print('Decoder review trip '+trip_id,flush=True)
                contexts[trip_id]=load_context(trips[trip_id],args.data/'student_test'/trip_id,model,model_config,config)
            context=contexts[trip_id];result=candidates.get((trip_id,best)) or run_decoder(context,best,config)
            for name,metrics in [('classifier_only',context['classifier_metrics']),('hmm_viterbi',result['metrics'])]:
                results.append(dict(trip_id=trip_id,subset=subset,method=name,**metrics,
                                    classifier_seconds=context['classifier_seconds'],transition_preparation_seconds=context['transition_seconds'],
                                    viterbi_seconds=result['decode_seconds'] if name=='hmm_viterbi' else 0))
            predictions=[dict(observation_id=i,classifier_arc=a['predicted_arc'],hmm_arc=b['predicted_arc'],
                              hmm_segment=b['segment_id'],hmm_reset=b['reset_reason'],weak_reference_arc=label['arc_id'])
                         for i,(a,b,label) in enumerate(zip(context['classifier'],result['predictions'],context['labels']))]
            write_csv(args.output/f'{trip_id}_predictions.csv',predictions)
            (args.output/f'{trip_id}_routes.json').write_text(json.dumps({'classifier_parts':context['classifier_parts'],'hmm_parts':result['parts']},indent=2)+'\n')
            route_map(trips[trip_id],context['classifier_parts'],result['parts'],args.maps/f'{trip_id}.html')
            write_csv(args.output/'comparison.csv',results)
            print(f"{trip_id}: classifier {context['classifier_metrics']['weak_reference_top1']:.4f}, HMM {result['metrics']['weak_reference_top1']:.4f}",flush=True)
            # Free bounded routing caches after final output for each trip.
            context['network'].cache.clear()
    summary={}
    for subset in ['selection','review','all']:
        summary[subset]={}
        for method in ['classifier_only','hmm_viterbi']:
            rows=[r for r in results if r['method']==method and (subset=='all' or r['subset']==subset)]
            total=sum(r['accepted_weak_labels'] for r in rows);pairs=sum(r['temporal_pairs'] for r in rows)
            summary[subset][method]={'trips':len(rows),'weak_reference_top1':sum(r['correct_weak_labels'] for r in rows)/total,
                'mean_trip_weak_reference_top1':float(np.mean([r['weak_reference_top1'] for r in rows])),
                'direct_continuity':sum(r['directly_joined_pairs'] for r in rows)/pairs if pairs else None,
                'mean_reference_sequence_edit_similarity':float(np.mean([r['reference_sequence_edit_similarity'] for r in rows])),
                'mean_reference_arc_set_f1':float(np.mean([r['reference_arc_set_f1'] for r in rows])),
                'total_route_parts':sum(r['route_parts'] for r in rows),'accepted_weak_labels':total,
                'decoder_unreachable_resets':sum(r['decoder_unreachable_resets'] for r in rows)}
    (args.output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
