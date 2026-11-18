"""TPE Bayesian search using training-trip CV, then frozen student-test evaluation."""
import argparse
import csv
import hashlib
import json
import platform
from pathlib import Path
import time
import joblib
import numpy as np
import optuna
from optuna.trial import TrialState
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import GroupKFold
from threadpoolctl import threadpool_limits
import sklearn
from pathsnap.models.dataset import load_dataset
from pathsnap.models.experiments import score, observation_results, write_csv, sha256
from pathsnap.features.preprocessing import FEATURES
from pathsnap.data.loading import load_trips


def suggest_parameters(trial, config):
    space=config['search_space']
    return {**{key:trial.suggest_int(key,**space[key]) for key in ['n_estimators','max_depth','min_samples_leaf']},
            'max_features':trial.suggest_categorical('max_features',space['max_features'])}


def make_objective(training, folds, config):
    """No student-test/evaluator inputs exist at this boundary."""
    def objective(trial):
        parameters=suggest_parameters(trial,config)
        records=[]
        for fold,(fit,validation) in enumerate(folds):
            if set(training.groups[fit])&set(training.groups[validation]):raise ValueError('Trip leakage in CV')
            model=RandomForestClassifier(**parameters,random_state=config['seed'],n_jobs=config['threads'])
            start=time.perf_counter();model.fit(training.X[fit],training.y[fit]);fit_time=time.perf_counter()-start
            start=time.perf_counter();prob=model.predict_proba(training.X[validation])[:,1];inference_time=time.perf_counter()-start
            metrics=score(training.y[validation],prob)
            records.append(dict(fold=fold,macro_f1=metrics['macro_f1'],log_loss=metrics['log_loss'],
                                fit_seconds=fit_time,inference_seconds=inference_time))
        trial.set_user_attr('folds',records)
        trial.set_user_attr('cv_macro_f1_std',float(np.std([r['macro_f1'] for r in records])))
        return float(np.mean([r['macro_f1'] for r in records]))
    return objective


def export_trials(study, output):
    records=[];details=[]
    for trial in study.trials:
        records.append(dict(trial=trial.number,state=trial.state.name,cv_macro_f1=trial.value,
                            cv_macro_f1_std=trial.user_attrs.get('cv_macro_f1_std'),**trial.params,
                            cv_fit_seconds=sum(r['fit_seconds'] for r in trial.user_attrs.get('folds',[])),
                            cv_inference_seconds=sum(r['inference_seconds'] for r in trial.user_attrs.get('folds',[]))))
        details.append(dict(trial=trial.number,state=trial.state.name,value=trial.value,parameters=trial.params,user_attributes=trial.user_attrs))
    if records:
        # Fixed columns also represent an interrupted trial with incomplete parameters.
        fields=['trial','state','cv_macro_f1','cv_macro_f1_std','n_estimators','max_depth','min_samples_leaf','max_features','cv_fit_seconds','cv_inference_seconds']
        with (output/'trials.csv').open('w',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=fields,lineterminator='\n');writer.writeheader();writer.writerows(records)
    (output/'trials.json').write_text(json.dumps(details,indent=2)+'\n')


def validate_inputs(data, raw_source, baseline):
    """Require exactly the previously measured development inputs, never held-out data."""
    if not raw_source.is_file() or sha256(raw_source)!=baseline['raw_source_sha256']:
        raise ValueError('Source must match the original development ZIP, not evaluator_test.zip')
    actual={str(p.relative_to(data)):sha256(p) for p in sorted(data.glob('*/*/*.jsonl.gz'))}
    if actual!=baseline['input_sha256']:raise ValueError('Processed development inputs differ from the Step 5 baseline')


def evaluate(model,data,arcs,threshold):
    start=time.perf_counter();prob=model.predict_proba(data.X)[:,1];elapsed=time.perf_counter()-start
    mask=np.zeros(len(data.y),dtype=bool)
    for row in data.observations:
        if row['reference'] is not None:mask[row['begin']:row['end']]=True
    classification=score(data.y[mask],prob[mask],threshold)
    predictions,sequence=observation_results(data,prob,arcs)
    return classification,sequence,predictions,elapsed


def plot(study,path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    trials=[t for t in study.trials if t.state==TrialState.COMPLETE]
    values=[t.value for t in trials]
    fig,ax=plt.subplots(figsize=(8,4),layout='constrained')
    ax.plot([t.number for t in trials],values,'o-',label='Completed trial CV F1')
    ax.plot([t.number for t in trials],np.maximum.accumulate(values),'--',label='Best so far')
    ax.set(title='TPE search: actual trip-grouped CV results',xlabel='Trial number (0 = untuned control)',ylabel='Weak-label candidate Macro F1')
    ax.legend();fig.savefig(path,dpi=160);plt.close(fig)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True,help='Original Student folder.zip only')
    parser.add_argument('--data',type=Path,default=Path('data/processed/step4'))
    parser.add_argument('--config',type=Path,default=Path('configs/bayesian_search.json'))
    parser.add_argument('--baseline',type=Path,default=Path('results/experiments/model_comparison'))
    parser.add_argument('--output',type=Path,default=Path('results/experiments/bayesian_optimization'))
    parser.add_argument('--artifacts',type=Path,default=Path('artifacts/bayesian_optimization'))
    parser.add_argument('--selected-config',type=Path,default=Path('configs/tuned_model.json'))
    args=parser.parse_args();config=json.loads(args.config.read_text())
    if args.output.resolve()==args.baseline.resolve():raise ValueError('Preserve baseline results: choose a separate output directory')
    if args.selected_config.resolve()==Path('configs/selected_model.json').resolve():raise ValueError('Preserve untuned selected config: choose a separate tuned output')
    baseline=json.loads((args.baseline/'manifest.json').read_text())
    selected=json.loads(Path('configs/selected_model.json').read_text())
    if selected['model_name']!='random_forest' or selected['candidate_binary_threshold']!=.5 or config['seed']!=selected['model_parameters']['random_state']:
        raise ValueError('Preserve selected baseline family, seed and threshold')
    if config['objective']!='mean_grouped_cv_macro_f1' or config['cv_folds']!=3 or config['n_trials']<4:
        raise ValueError('Require declared objective, original 3 folds and at least 4 trials')
    if not 1<=config['n_startup_trials']<config['n_trials']:raise ValueError('Require startup control and adaptive TPE trials')
    if config['threads']<1:raise ValueError('threads must be positive')
    validate_inputs(args.data,args.source,baseline)
    training=load_dataset(args.data,'train',None,config['seed'])
    if len(training.coverage)!=80 or len(training.observations)!=baseline['training_observations']:raise ValueError('Training coverage mismatch')
    folds=list(GroupKFold(config['cv_folds']).split(training.X,training.y,training.groups))
    for i,(fit,validation) in enumerate(folds):
        recorded=baseline['folds'][i]
        if set(training.groups[fit])!=set(recorded['fit_trips']) or set(training.groups[validation])!=set(recorded['validation_trips']):
            raise ValueError('Fold assignments differ from baseline')
    args.output.mkdir(parents=True,exist_ok=True);args.artifacts.mkdir(parents=True,exist_ok=True)
    context={'search':config,'features':FEATURES,'training_observations':len(training.observations),
             'training_candidate_rows':len(training.y),'folds':baseline['folds'],'input_sha256':baseline['input_sha256'],
             'baseline_parameters':selected['model_parameters'],'python':platform.python_version(),
             'sklearn':sklearn.__version__,'optuna':optuna.__version__,
             'data_policy':'Training CV only; student test loaded after parameters are frozen; evaluator archive excluded.'}
    context_hash=hashlib.sha256(json.dumps(context,sort_keys=True).encode()).hexdigest()
    storage='sqlite:///'+str((args.artifacts/'study.sqlite3').resolve())
    sampler=optuna.samplers.TPESampler(seed=config['seed'],n_startup_trials=config['n_startup_trials'])
    study=optuna.create_study(study_name=config['study_name'],storage=storage,direction='maximize',sampler=sampler,load_if_exists=True)
    existing=study.user_attrs.get('context_sha256')
    if existing is not None and existing!=context_hash:raise ValueError('Study context changed; use a new study/artifact directory')
    study.set_user_attr('context_sha256',context_hash)
    (args.output/'manifest.json').write_text(json.dumps({**context,'context_sha256':context_hash},indent=2)+'\n')
    if not study.trials:
        params=selected['model_parameters']
        study.enqueue_trial({k:params.get(k,'sqrt') for k in ['n_estimators','max_depth','min_samples_leaf','max_features']})
    remaining=config['n_trials']-sum(t.state!=TrialState.WAITING for t in study.trials)
    with threadpool_limits(limits=config['threads']):
        if remaining>0:
            study.optimize(make_objective(training,folds,config),n_trials=remaining,
                           callbacks=[lambda s,t:export_trials(s,args.output)],gc_after_trial=True)
        if any(t.state!=TrialState.COMPLETE for t in study.trials):
            raise RuntimeError('Incomplete/failed trials retained; investigate before final evaluation')
        if len(study.trials)!=config['n_trials']:raise ValueError('Unexpected trial budget')
        export_trials(study,args.output)
        best=study.best_trial
        # Freeze tuning decision before reading student-test features or references.
        decision={'model':'random_forest','trial':best.number,'parameters':best.params,'cv_macro_f1':best.value,
                  'cv_macro_f1_std':best.user_attrs['cv_macro_f1_std'],'selection_data':'training trip-grouped CV only'}
        (args.output/'best_trial.json').write_text(json.dumps(decision,indent=2)+'\n')
        testing=load_dataset(args.data,'student_test')
        if len(testing.coverage)!=10:raise ValueError('Expected ten student-test trips')
        arcs={}
        for trip in load_trips(args.source):
            if trip.partition=='student_test':arcs[trip.trip_id]=trip.rows['arcs']
            if len(arcs)==10:break
        records=[]
        for label,parameters,cv_value in [('untuned',selected['model_parameters'],study.trials[0].value),
                                          ('tuned',{**best.params,'random_state':config['seed'],'n_jobs':config['threads']},best.value)]:
            model=RandomForestClassifier(**parameters)
            start=time.perf_counter();model.fit(training.X,training.y);fit_time=time.perf_counter()-start
            classification,sequence,predictions,inference_time=evaluate(model,testing,arcs,selected['candidate_binary_threshold'])
            joblib.dump(model,args.artifacts/f'{label}.joblib')
            write_csv(args.output/f'{label}_predictions.csv',predictions)
            (args.output/f'{label}_metrics.json').write_text(json.dumps({'parameters':parameters,'classification':classification,'sequence':sequence},indent=2)+'\n')
            records.append(dict(model=label,cv_macro_f1=cv_value,student_macro_f1=classification['macro_f1'],
                                student_weak_reference_top1=sequence['weak_reference_top1'],student_log_loss=classification['log_loss'],
                                direct_route_continuity=sequence['direct_route_continuity'],fit_seconds=fit_time,inference_seconds=inference_time))
        write_csv(args.output/'tuned_vs_untuned.csv',records)
    chosen={**selected,'stage':'bayesian_tuned_baseline','model_parameters':{**best.params,'random_state':config['seed'],'n_jobs':config['threads']},
            'evidence':str(args.output/'best_trial.json'),'next_stage':'HMM/Viterbi route reconstruction and classifier-only comparison'}
    args.selected_config.parent.mkdir(parents=True,exist_ok=True)
    args.selected_config.write_text(json.dumps(chosen,indent=2)+'\n')
    plot(study,args.output/'optimization_history.png')
    print(json.dumps({'best_trial':decision,'comparison':records,'total_cv_fit_seconds':sum(r['fit_seconds'] for t in study.trials for r in t.user_attrs['folds'])},indent=2))


if __name__=='__main__':main()
