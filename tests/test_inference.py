import json
from importlib import metadata
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from pathsnap.features.candidates import FEATURES
from pathsnap.inference.bundle import load_bundle,file_hash,PREPROCESSING_KEYS,HMM_KEYS,RUNTIME_DEPENDENCIES
from pathsnap.inference.export import export_bundle
from pathsnap.inference.io import read_inputs


class InferenceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        (self.root/'configs').mkdir()
        parameters={'n_estimators':2,'max_depth':2,'random_state':42,'n_jobs':1}
        X=np.random.default_rng(42).normal(size=(30,len(FEATURES)));y=np.tile([0,1],15)
        joblib.dump(RandomForestClassifier(**parameters).fit(X,y),self.root/'model.joblib')
        pre=json.loads(Path('configs/preprocessing.json').read_text());hmm=json.loads(Path('configs/hmm.json').read_text())
        for name,values in [('preprocessing',{k:pre[k] for k in PREPROCESSING_KEYS}),('hmm',{k:hmm[k] for k in HMM_KEYS}),
                            ('model',{'model_name':'random_forest','model_parameters':parameters,'positive_class':1,'feature_columns':FEATURES})]:
            (self.root/f'configs/{name}.json').write_text(json.dumps(values))
        (self.root/'requirements.txt').write_text('fixture\n');(self.root/'run_inference.py').write_text('# fixture\n')
        self.manifest={'schema_version':1,'bundle_version':'test','python_major_minor':list(sys.version_info[:2]),
                       'reference_data_included':False,'runtime_versions':{name:metadata.version(name) for name in RUNTIME_DEPENDENCIES},
                       'files':{str(p.relative_to(self.root)):file_hash(p) for p in self.root.rglob('*') if p.is_file()}}
        self.save_manifest()

    def tearDown(self):self.temp.cleanup()

    def save_manifest(self):
        (self.root/'manifest.json').write_text(json.dumps(self.manifest))

    def test_label_free_prediction_keeps_invalid_and_missing_observations(self):
        predictor=load_bundle(self.root)
        result=predictor.predict([(0,0,1),None,(1,1,3)],[(0,0),(.001,0)],[(0,1)])
        self.assertEqual(len(result['observations']),3)
        self.assertIsNone(result['observations'][1]['predicted_arc_id'])
        self.assertIsNone(result['observations'][2]['predicted_arc_id'])
        self.assertEqual(result['diagnostics']['invalid_observations'],1)
        self.assertNotIn('accuracy',result)
        with self.assertRaises(TypeError):predictor.predict([],[],[],route=[1])

    def test_corruption_fails_before_deserializing(self):
        with (self.root/'model.joblib').open('ab') as stream:stream.write(b'corrupt')
        with patch('joblib.load') as unpickle:
            with self.assertRaisesRegex(ValueError,'checksum'):load_bundle(self.root)
            unpickle.assert_not_called()

    def test_missing_file_and_wrong_runtime_are_rejected(self):
        self.manifest['runtime_versions']['numpy']='0.0.0';self.save_manifest()
        with self.assertRaisesRegex(ValueError,'requirements'):load_bundle(self.root)
        self.manifest['runtime_versions']['numpy']=metadata.version('numpy');self.save_manifest()
        (self.root/'configs/hmm.json').unlink()
        with self.assertRaisesRegex(ValueError,'Missing/invalid'):load_bundle(self.root)

    def test_feature_order_mismatch_rejected_before_deserializing(self):
        path=self.root/'configs/model.json';value=json.loads(path.read_text());value['feature_columns']=list(reversed(FEATURES));path.write_text(json.dumps(value))
        self.manifest['files']['configs/model.json']=file_hash(path);self.save_manifest()
        with patch('joblib.load') as unpickle:
            with self.assertRaisesRegex(ValueError,'Feature order'):load_bundle(self.root)
            unpickle.assert_not_called()

    def test_geometry_rejects_fractional_ids_and_empty_track(self):
        predictor=load_bundle(self.root)
        with self.assertRaisesRegex(ValueError,'integer'):predictor.predict([(0,0,1)],[(0,0),(.001,0)],[(0,1.5)])
        with self.assertRaisesRegex(ValueError,'at least one'):predictor.predict([],[(0,0),(.001,0)],[(0,1)])

    def test_trip_reader_never_reads_reference(self):
        folder=self.root/'trip';folder.mkdir()
        for kind,text in [('track','0 0 1\nbad\n'),('nodes','0 0\n.001 0\n'),('arcs','0 1\n'),('route','DO NOT READ')]:
            (folder/f'trip.{kind}').write_text(text)
        original=Path.read_text
        def guarded(path,*args,**kwargs):
            if path.suffix=='.route':raise AssertionError('Reference file was accessed')
            return original(path,*args,**kwargs)
        with patch.object(Path,'read_text',guarded):track,nodes,arcs=read_inputs(folder)
        self.assertEqual(len(track),2);self.assertIsNone(track[1]);self.assertEqual(arcs,[(0,1)])

    def test_export_refuses_to_replace_existing_release(self):
        (self.root/'pathsnap-existing').mkdir()
        with self.assertRaises(FileExistsError):export_bundle(Path.cwd(),self.root/'model.joblib',self.root,'existing')
