import gzip
import json
import tempfile
import unittest
from pathlib import Path
import numpy as np
from sklearn.model_selection import GroupKFold
from threadpoolctl import threadpool_limits
from pathsnap.features.preprocessing import FEATURES
from pathsnap.models.dataset import Dataset, load_dataset
from pathsnap.models.experiments import factories, observation_results, score


class ModelTests(unittest.TestCase):
    def test_five_models_produce_probabilities(self):
        config=json.loads(Path('configs/model_experiments.json').read_text())
        rng=np.random.default_rng(42);X=rng.normal(size=(120,len(FEATURES)));y=(X[:,0]>0).astype(int)
        groups=np.repeat(np.arange(6),20)
        train,validation=next(GroupKFold(3).split(X,y,groups))
        self.assertFalse(set(groups[train])&set(groups[validation]))
        models=factories(config);self.assertEqual(len(models),5)
        with threadpool_limits(limits=2):
            for _,model in models.values():
                model.fit(X[train],y[train]);p=model.predict_proba(X[validation])[:,1]
                self.assertTrue(np.isfinite(p).all());self.assertTrue(((p>=0)&(p<=1)).all())
                self.assertTrue(np.isfinite(score(y[validation],p)['log_loss']))

    def test_top1_counts_misses_and_does_not_cross_gap(self):
        observations=[dict(trip_id='a',observation_id=0,reference=2,begin=0,end=2,arc_ids=[1,2],gap_reset=True),
                      dict(trip_id='a',observation_id=1,reference=3,begin=2,end=2,arc_ids=[],gap_reset=True)]
        data=Dataset(np.zeros((2,10)),np.array([0,1]),np.array(['a','a']),observations,[])
        rows,metrics=observation_results(data,np.array([.1,.9]),{'a':[(0,0),(0,1),(1,2),(2,3)]})
        self.assertEqual(metrics['weak_reference_top1'],.5)
        self.assertEqual(metrics['eligible_consecutive_pairs'],0)
        self.assertIsNone(rows[1]['predicted_arc'])

    def test_loader_sampling_and_reference_separation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);folder=root/'train/a';folder.mkdir(parents=True)
            candidate={'arc_id':1,**dict.fromkeys(FEATURES,0.0)}
            obs=[{'observation_id':i,'candidates':[candidate]} for i in range(5)]
            labels=[{'observation_id':i,'arc_id':1 if i<3 else None} for i in range(5)]
            for name,rows in [('observations',obs),('weak_labels',labels)]:
                with gzip.open(folder/f'{name}.jsonl.gz','wt') as f:
                    for row in rows:f.write(json.dumps(row)+'\n')
            data=load_dataset(root,'train',limit=2)
            self.assertEqual(len(data.observations),2)
            self.assertEqual(data.X.shape,(2,len(FEATURES)))
            self.assertTrue((data.X==0).all());self.assertTrue((data.y==1).all())
            self.assertEqual(data.coverage[0]['accepted_labels'],3)
