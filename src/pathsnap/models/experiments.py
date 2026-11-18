"""Five-model grouped CV and full student-test weak-reference evaluation."""
import argparse
import hashlib
import csv
import json
import platform
from pathlib import Path
import time
import joblib
import numpy as np
import sklearn
from sklearn.base import clone
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import GaussianNB
from sklearn.tree import DecisionTreeClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import GroupKFold
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, log_loss, confusion_matrix
from threadpoolctl import threadpool_limits
from pathsnap.features.preprocessing import FEATURES
from pathsnap.models.dataset import load_dataset
from pathsnap.data.loading import load_trips


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def factories(config):
    p=config['models'];seed=config['seed']
    return {
        'logistic_regression':('linear',make_pipeline(StandardScaler(),LogisticRegression(**p['logistic_regression'],random_state=seed))),
        'gaussian_nb':('probabilistic',make_pipeline(StandardScaler(),GaussianNB(**p['gaussian_nb']))),
        'decision_tree':('tree',DecisionTreeClassifier(**p['decision_tree'],random_state=seed)),
        'random_forest':('ensemble',RandomForestClassifier(**p['random_forest'],random_state=seed,n_jobs=config['threads'])),
        'hist_gradient_boosting':('boosting',HistGradientBoostingClassifier(**p['hist_gradient_boosting'],random_state=seed))}


def score(y, probability, threshold=.5):
    prediction=(probability>=threshold).astype(int)
    precision,recall,f1,_=precision_recall_fscore_support(y,prediction,average='macro',labels=[0,1],zero_division=0)
    return dict(accuracy=float(accuracy_score(y,prediction)),macro_precision=float(precision),macro_recall=float(recall),
                macro_f1=float(f1),log_loss=float(log_loss(y,np.column_stack((1-probability,probability)),labels=[0,1])),
                confusion_matrix=confusion_matrix(y,prediction,labels=[0,1]).tolist())


def observation_results(data, probability, arcs):
    rows=[];correct=0;accepted=0;joined=0;pairs=0;previous={}
    for row in data.observations:
        begin,end=row['begin'],row['end'];predicted=None
        if end>begin:predicted=row['arc_ids'][int(np.argmax(probability[begin:end]))]
        if row['reference'] is not None:
            accepted+=1;correct+=predicted==row['reference']
        last=previous.get(row['trip_id'])
        if last and last['observation_id']+1==row['observation_id'] and not row['gap_reset'] and predicted is not None and last['predicted_arc'] is not None:
            pairs+=1;a=last['predicted_arc'];b=predicted
            joined+=a==b or arcs[row['trip_id']][a][1]==arcs[row['trip_id']][b][0]
        output=dict(trip_id=row['trip_id'],observation_id=row['observation_id'],predicted_arc=predicted,weak_reference_arc=row['reference'])
        rows.append(output);previous[row['trip_id']]=output
    return rows,dict(weak_reference_top1=correct/accepted if accepted else None,accepted_reference_observations=accepted,
                     directly_continuous_pairs=joined,eligible_consecutive_pairs=pairs,
                     direct_route_continuity=joined/pairs if pairs else None)


def write_csv(path,rows):
    with path.open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=rows[0],lineterminator='\n');writer.writeheader();writer.writerows(rows)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data',type=Path,default=Path('data/processed/step4'))
    parser.add_argument('--source',type=Path,required=True,help='Original development ZIP, for student road connectivity')
    parser.add_argument('--config',type=Path,default=Path('configs/model_experiments.json'))
    parser.add_argument('--output',type=Path,default=Path('results/experiments/model_comparison'))
    parser.add_argument('--artifacts',type=Path,default=Path('artifacts/model_comparison'))
    args=parser.parse_args();config=json.loads(args.config.read_text())
    if config['selection_metric']!='cv_macro_f1':raise ValueError('Unsupported selection metric')
    args.output.mkdir(parents=True,exist_ok=True);args.artifacts.mkdir(parents=True,exist_ok=True)
    training=load_dataset(args.data,'train',config['max_training_observations_per_trip'],config['seed'])
    testing=load_dataset(args.data,'student_test')
    if {r['trip_id'] for r in training.coverage}&{r['trip_id'] for r in testing.coverage}:raise ValueError('Partition trip overlap')
    if len(training.coverage)!=80 or len(testing.coverage)!=10:raise ValueError('Expected 80 train and 10 student-test trips')
    if set(np.unique(training.y))!={0,1}:raise ValueError('Both classes required')
    arcs={}
    for trip in load_trips(args.source):
        if trip.partition=='student_test':arcs[trip.trip_id]=trip.rows['arcs']
        if len(arcs)==10:break
    if set(arcs)!={r['trip_id'] for r in testing.coverage}:raise ValueError('Student road networks missing')
    manifest={'config':config,'features':FEATURES,'python':platform.python_version(),'sklearn':sklearn.__version__,
              'label_warning':'All classification scores measure weak geometric labels, not verified GPS ground truth.',
              'training_candidate_rows':len(training.y),'training_observations':len(training.observations),
              'eligible_training_trip_groups':len(np.unique(training.groups)),
              'training_coverage':training.coverage,'student_test_coverage':testing.coverage,
              'folds':[]}
    folds=list(GroupKFold(n_splits=config['cv_folds']).split(training.X,training.y,training.groups))
    for i,(fit,validation) in enumerate(folds):
        fit_groups=sorted(set(training.groups[fit]));val_groups=sorted(set(training.groups[validation]))
        assert not set(fit_groups)&set(val_groups)
        manifest['folds'].append({'fold':i,'fit_trips':fit_groups,'validation_trips':val_groups})
    manifest['input_sha256'] = {str(path.relative_to(args.data)): sha256(path) for path in sorted(args.data.glob('*/*/*.jsonl.gz'))}
    manifest['raw_source_sha256'] = sha256(args.source) if args.source.is_file() else None
    (args.output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    comparison=[];cv_records=[]
    with threadpool_limits(limits=config['threads']):
        for name,(family,base) in factories(config).items():
            print('Training '+name,flush=True);fold_f1=[]
            for fold,(fit,validation) in enumerate(folds):
                model=clone(base);start=time.perf_counter();model.fit(training.X[fit],training.y[fit]);fit_time=time.perf_counter()-start
                start=time.perf_counter();prob=model.predict_proba(training.X[validation])[:,1];infer_time=time.perf_counter()-start
                metrics=score(training.y[validation],prob,config['probability_threshold'])
                train_metrics=score(training.y[fit],model.predict_proba(training.X[fit])[:,1],config['probability_threshold'])
                cv_records.append(dict(model=name,fold=fold,train_macro_f1=train_metrics['macro_f1'],validation_macro_f1=metrics['macro_f1'],
                                       validation_log_loss=metrics['log_loss'],fit_seconds=fit_time,inference_seconds=infer_time))
                fold_f1.append(metrics['macro_f1']);write_csv(args.output/'cv_results.csv',cv_records)
            model=clone(base);start=time.perf_counter();model.fit(training.X,training.y);fit_time=time.perf_counter()-start
            start=time.perf_counter();prob=model.predict_proba(testing.X)[:,1];infer_time=time.perf_counter()-start
            # Evaluation classification is conditional on accepted reference labels.
            mask=np.zeros(len(testing.y),dtype=bool)
            for row in testing.observations:
                if row['reference'] is not None:mask[row['begin']:row['end']]=True
            metrics=score(testing.y[mask],prob[mask],config['probability_threshold'])
            predictions,sequence=observation_results(testing,prob,arcs)
            write_csv(args.output/f'{name}_predictions.csv',predictions)
            detail={'model':name,'family':family,'configuration':config['models'][name],'classification':metrics,'sequence':sequence}
            (args.output/f'{name}_metrics.json').write_text(json.dumps(detail,indent=2)+'\n')
            per_trip=[]
            for trip_id in sorted(arcs):
                accepted=[r for r in predictions if r['trip_id']==trip_id and r['weak_reference_arc'] is not None]
                per_trip.append(dict(trip_id=trip_id,accepted_weak_labels=len(accepted),
                                     weak_reference_top1=sum(r['predicted_arc']==r['weak_reference_arc'] for r in accepted)/len(accepted) if accepted else None))
            write_csv(args.output/f'{name}_per_trip.csv',per_trip)
            joblib.dump(model,args.artifacts/f'{name}.joblib')
            comparison.append(dict(model=name,family=family,cv_macro_f1_mean=float(np.mean(fold_f1)),cv_macro_f1_std=float(np.std(fold_f1)),
                                   student_macro_f1=metrics['macro_f1'],student_macro_precision=metrics['macro_precision'],student_macro_recall=metrics['macro_recall'],
                                   student_log_loss=metrics['log_loss'],student_weak_reference_top1=sequence['weak_reference_top1'],
                                   direct_route_continuity=sequence['direct_route_continuity'],fit_seconds=fit_time,inference_seconds=infer_time))
            write_csv(args.output/'comparison.csv',comparison)
    selected=max(comparison,key=lambda r:r['cv_macro_f1_mean'])
    (args.output/'selection.json').write_text(json.dumps({'selected_model':selected['model'],'primary_metric':'mean grouped-CV candidate Macro F1',
        'scope':'baseline comparison with weak labels; training cap (null means full) recorded in manifest; not Bayesian tuned','reason':'Highest predeclared grouped-CV Macro F1; student-test scores were not used for selection.'},indent=2)+'\n')
    plot(comparison,args.output/'comparison.png')
    print(json.dumps(selected,indent=2))


def plot(rows,path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,4,figsize=(18,5),layout='constrained')
    names=[r['model'].replace('_','\n') for r in rows]
    for ax,key,title in zip(axes,['cv_macro_f1_mean','student_weak_reference_top1','student_macro_f1','student_log_loss'],['Grouped CV Macro F1','Student weak-reference Top-1','Student-test Macro F1','Student-test log loss']):
        ax.bar(names,[r[key] for r in rows],color='#287c66');ax.set_title(title);ax.tick_params(axis='x',labelsize=8)
        if key!='student_log_loss':ax.set_ylim(0,1)
    fig.suptitle('Baseline comparison: weak-reference metrics (see manifest for training scope)')
    fig.savefig(path,dpi=160);plt.close(fig)


if __name__=='__main__':main()
