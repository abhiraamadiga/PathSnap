from contextlib import contextmanager
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from fastapi.testclient import TestClient
from pathsnap.api.app import create_app
from pathsnap.api.settings import Settings
from pathsnap.api.store import TripStore
from pathsnap.evaluation.scoring import score_prediction

SECRET='PRIVATE_REFERENCE_SHOULD_NOT_LEAVE_SERVER'


class FakePredictor:
    manifest={'files':{},'bundle_version':'test'}
    def __init__(self,events):self.events=events;self.fail=False
    def predict(self,track,nodes,arcs):
        self.events.append('predict')
        if self.fail:raise ValueError(SECRET)
        return {'schema_version':1,'bundle_version':'test','observations':[
            {'observation_id':i,'status':'ok','candidate_count':1,'classifier_arc_id':0,'predicted_arc_id':0,
             'segment_id':0,'reset_reason':'start' if i==0 else None,'private_reference':SECRET} for i in range(len(track))],
            'route_parts':[{'arc_ids':[0],'geometry':{'type':'MultiLineString','coordinates':[[nodes[0],nodes[1]]]}}],
            'diagnostics':{'observation_count':len(track)},'prediction_seconds':.01,'reference_route':[SECRET]}


class APITests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.events=[];self.loads=0
        self.archive=self.root/'development.zip';self.ids=[f'{i:08d}' for i in range(10)]
        with zipfile.ZipFile(self.archive,'w') as z:
            for trip in self.ids:
                for kind,raw in [('track','0.0001 0 1\n0.0002 0 2\n'),('nodes','0 0\n0.001 0\n'),('arcs','0 1\n'),('route','0\n')]:
                    z.writestr(f'Student folder/student_test/{trip}/{trip}.{kind}',raw)
        self.registry=self.root/'registry.json'
        self.registry.write_text(json.dumps({'partition':'student_test','trip_ids':self.ids,'archive_sha256':hashlib.sha256(self.archive.read_bytes()).hexdigest()}))
        self.ref=self.root/'reference.json';self.ref.write_text(Path('configs/preprocessing.json').read_text())
        self.settings=Settings(self.root/'bundle',self.archive,self.registry,self.ref)
        self.predictor=FakePredictor(self.events)

    def tearDown(self):self.temp.cleanup()

    def loader(self,path):self.loads+=1;return self.predictor

    def scorer(self,*args):
        self.events.append('score')
        return {'status':'ok','total_observations':2,'evaluated_observations':2,'hmm_weak_reference_top1':1.0,
                'note':'weak labels','reference_route':[SECRET]}

    @contextmanager
    def running(self,settings=None,scorer=None):
        app=create_app(settings or self.settings,predictor_loader=self.loader,scorer=scorer or self.scorer)
        with self.assertLogs('pathsnap.api',level='INFO') as logs:
            with TestClient(app) as client:yield client,app,logs

    def test_health_listing_and_repeated_real_pipeline_calls(self):
        with self.running() as (client,app,logs):
            with patch.object(app.state.store,'read_inputs',side_effect=AssertionError('No payload reads for listing')):
                self.assertEqual(client.get('/healthz').status_code,200)
                self.assertEqual(client.get('/readyz').json()['status'],'ready')
                self.assertEqual(client.get('/trips').json()['trip_ids'],self.ids)
            for _ in range(2):
                response=client.post('/predict',json={'trip_id':self.ids[0]})
                self.assertEqual(response.status_code,200)
                self.assertEqual(response.headers['X-Request-ID'],response.json()['request_id'])
                self.assertNotIn(SECRET,response.text)
                self.assertNotIn('reference_route',response.json()['prediction'])
            self.assertEqual(self.loads,1)
            self.assertEqual(self.events,['predict','score','predict','score'])
        self.assertTrue(any('inference_started' in line and 'trip_id=00000000' in line for line in logs.output))

    def test_validation_and_unknown_trip_do_not_run_inference(self):
        with self.running() as (client,app,logs):
            for body in [{'trip_id':'../route'},{'trip_id':self.ids[0],'route':[SECRET]},{'trip_id':123}]:
                response=client.post('/predict',json=body);self.assertEqual(response.status_code,422);self.assertNotIn(SECRET,response.text)
            self.assertEqual(client.post('/predict',json={'trip_id':'99999999'}).status_code,404)
            self.assertEqual(self.events,[])

    def test_prediction_precedes_reference_read(self):
        with self.running() as (client,app,logs):
            original=app.state.store.read_reference
            def reference(trip):self.events.append('read_reference');return original(trip)
            with patch.object(app.state.store,'read_reference',reference):
                self.assertEqual(client.post('/predict',json={'trip_id':self.ids[0]}).status_code,200)
            self.assertEqual(self.events,['predict','read_reference','score'])

    def test_busy_and_failure_responses_are_safe_and_lock_releases(self):
        with self.running() as (client,app,logs):
            app.state.predict_lock.acquire()
            response=client.post('/predict',json={'trip_id':self.ids[0]})
            self.assertEqual(response.status_code,503);self.assertEqual(response.headers['Retry-After'],'1')
            app.state.predict_lock.release();self.predictor.fail=True
            response=client.post('/predict',json={'trip_id':self.ids[0]})
            self.assertEqual(response.status_code,503);self.assertNotIn(SECRET,response.text)
            self.predictor.fail=False
            self.assertEqual(client.post('/predict',json={'trip_id':self.ids[0]}).status_code,200)

    def test_missing_or_invalid_reference_never_fakes_zero_accuracy(self):
        with self.running() as (client,app,logs):
            with patch.object(app.state.store,'read_reference',return_value=None):
                response=client.post('/predict',json={'trip_id':self.ids[0]})
                self.assertEqual(response.status_code,200);self.assertEqual(response.json()['evaluation']['status'],'reference_unavailable')
                self.assertIsNone(response.json()['evaluation']['hmm_weak_reference_top1'])
            with patch.object(app.state.store,'read_reference',side_effect=ValueError(SECRET)):
                response=client.post('/predict',json={'trip_id':self.ids[0]})
                self.assertEqual(response.json()['evaluation']['status'],'invalid_reference');self.assertNotIn(SECRET,response.text)

    def test_disabled_scoring_does_not_read_reference(self):
        with self.running(replace(self.settings,reference_scoring=False,reference_config_path=self.root/'absent.json')) as (client,app,logs):
            with patch.object(app.state.store,'read_reference',side_effect=AssertionError('No reference access')):
                response=client.post('/predict',json={'trip_id':self.ids[0]})
                self.assertEqual(response.json()['evaluation']['status'],'disabled')
            self.assertEqual(self.events,['predict'])

    def test_evaluator_listing_is_metadata_only_and_inference_is_gated(self):
        archive=self.root/'evaluator.zip'
        with zipfile.ZipFile(self.archive) as source,zipfile.ZipFile(archive,'w') as target:
            for name in source.namelist():target.writestr(name.replace('Student folder/student_test','evaluator_test'),source.read(name))
        registry=self.root/'evaluator.json';registry.write_text(json.dumps({'partition':'evaluator_test','trip_ids':self.ids,'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest()}))
        settings=replace(self.settings,archive_path=archive,registry_path=registry,partition='evaluator_test')
        with patch.object(zipfile.ZipFile,'read',side_effect=AssertionError('No evaluator payload access')):
            with self.running(settings) as (client,app,logs):
                self.assertFalse(client.get('/trips').json()['inference_enabled'])
                self.assertEqual(client.post('/predict',json={'trip_id':self.ids[0]}).status_code,409)
                self.assertEqual(self.events,[])

    def test_cors_is_explicit(self):
        with self.running() as (client,app,logs):
            headers={'Origin':'http://localhost:8501','Access-Control-Request-Method':'POST'}
            response=client.options('/predict',headers=headers)
            self.assertEqual(response.headers['access-control-allow-origin'],'http://localhost:8501')
            headers['Origin']='http://unlisted.example'
            self.assertNotIn('access-control-allow-origin',client.options('/predict',headers=headers).headers)

    def test_private_network_preflight_requires_opt_in_and_allowed_origin(self):
        headers = {'Origin': 'http://localhost:8501', 'Access-Control-Request-Method': 'POST',
                   'Access-Control-Request-Private-Network': 'true'}
        with self.running() as (client, _, _):
            self.assertEqual(client.options('/predict', headers=headers).status_code, 400)
        settings = replace(self.settings, cors_allow_private_network=True)
        with self.running(settings) as (client, _, _):
            response = client.options('/predict', headers=headers)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers['access-control-allow-private-network'], 'true')
            headers['Origin'] = 'http://unlisted.example'
            response = client.options('/predict', headers=headers)
            self.assertEqual(response.status_code, 400)
            self.assertNotIn('access-control-allow-origin', response.headers)
        with self.assertRaisesRegex(ValueError, 'explicit UI origins'):
            replace(settings, cors_origins=('*',))

    def test_trip_store_prediction_reader_excludes_route(self):
        store=TripStore(self.archive,self.registry,'student_test');original=store.read
        def guarded(trip,kind):
            self.assertNotEqual(kind,'route');return original(trip,kind)
        with patch.object(store,'read',guarded):
            track,nodes,arcs=store.read_inputs(self.ids[0])
        self.assertEqual(len(track),2);self.assertEqual(arcs,[(0,1)])
        with self.assertRaises(KeyError):store.read_inputs('../route')

    def test_registry_checksum_mismatch_fails_startup(self):
        registry=json.loads(self.registry.read_text());registry['archive_sha256']='bad';self.registry.write_text(json.dumps(registry))
        with self.assertRaisesRegex(ValueError,'checksum'):TripStore(self.archive,self.registry,'student_test')

    def test_private_scorer_returns_only_aggregates(self):
        track=[(.0001,0,1),(.0002,0,2)];nodes=[(0,0),(.001,0)];arcs=[(0,1)]
        prediction=self.predictor.predict(track,nodes,arcs)
        scores=score_prediction(track,nodes,arcs,[(0,)],prediction,json.loads(self.ref.read_text()))
        self.assertEqual(scores['hmm_weak_reference_top1'],1)
        self.assertEqual(scores['evaluated_observations'],2)
        self.assertNotIn('reference_route',scores)
        with self.assertRaises(ValueError):score_prediction(track,nodes,arcs,[(99,)],prediction,json.loads(self.ref.read_text()))
