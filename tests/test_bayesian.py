import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import optuna
from sklearn.model_selection import GroupKFold
from threadpoolctl import threadpool_limits
from pathsnap.optimization.bayesian import make_objective,validate_inputs,export_trials


class BayesianTests(unittest.TestCase):
    def test_training_only_grouped_objective_and_trial_export(self):
        rng=np.random.default_rng(42)
        X=rng.normal(size=(120,10));y=(X[:,0]>0).astype(int);groups=np.repeat(np.arange(6),20)
        train=SimpleNamespace(X=X,y=y,groups=groups)
        config={'seed':42,'threads':1,'search_space':{
            'n_estimators':{'low':4,'high':8,'step':4},'max_depth':{'low':2,'high':4,'step':2},
            'min_samples_leaf':{'low':1,'high':2,'step':1},'max_features':['sqrt',.5]}}
        folds=list(GroupKFold(3).split(X,y,groups))
        study=optuna.create_study(direction='maximize',sampler=optuna.samplers.TPESampler(seed=42,n_startup_trials=1))
        with threadpool_limits(limits=1):study.optimize(make_objective(train,folds,config),n_trials=2)
        self.assertEqual(len(study.trials),2)
        self.assertEqual(len(study.best_trial.user_attrs['folds']),3)
        self.assertTrue(0<=study.best_value<=1)
        with tempfile.TemporaryDirectory() as tmp:
            export_trials(study,Path(tmp))
            self.assertEqual(len(json.loads((Path(tmp)/'trials.json').read_text())),2)

    def test_evaluator_source_is_rejected_before_tuning(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'evaluator_test.zip';source.write_bytes(b'held-out placeholder')
            with self.assertRaisesRegex(ValueError,'development ZIP'):
                validate_inputs(Path(tmp),source,{'raw_source_sha256':'different'})

    def test_detect_changed_processed_input(self):
        from pathsnap.models.experiments import sha256
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'development.zip';source.write_bytes(b'development placeholder')
            with self.assertRaisesRegex(ValueError,'Processed development'):
                validate_inputs(root,source,{'raw_source_sha256':sha256(source),'input_sha256':{'expected':'missing'}})
