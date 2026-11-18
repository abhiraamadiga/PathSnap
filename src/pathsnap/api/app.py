"""Load one verified model per server process; infer before private scoring."""
from contextlib import asynccontextmanager
import json
import logging
import math
from pathlib import Path
from threading import Lock
import time
from uuid import uuid4
from fastapi import FastAPI,HTTPException,Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from pathsnap.api.settings import Settings
from pathsnap.api.store import TripStore
from pathsnap.api.schemas import PredictRequest,PredictResponse,HealthResponse,TripsResponse
from pathsnap.inference.bundle import load_bundle,file_hash
from pathsnap.inference.pipeline import normalise_track
from pathsnap.evaluation.scoring import score_prediction,unavailable

logger=logging.getLogger('pathsnap.api')


def verify_runtime_source(predictor):
    import pathsnap
    source=Path(pathsnap.__file__).resolve().parent
    for name,expected in predictor.manifest['files'].items():
        if name.startswith('pathsnap/'):
            path=source/name.removeprefix('pathsnap/')
            if not path.is_file() or file_hash(path)!=expected:raise ValueError('Installed inference source differs from frozen bundle')


def create_app(settings=None,*,predictor_loader=load_bundle,scorer=score_prediction,store_factory=TripStore):
    settings=settings or Settings.from_env()
    if not logger.handlers:
        handler=logging.StreamHandler();handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'));logger.addHandler(handler)
    logger.setLevel(logging.INFO);logger.propagate=False

    @asynccontextmanager
    async def lifespan(app):
        predictor=predictor_loader(settings.bundle_dir);verify_runtime_source(predictor)
        store=store_factory(settings.archive_path,settings.registry_path,settings.partition)
        app.state.predictor=predictor;app.state.store=store;app.state.predict_lock=Lock()
        app.state.reference_config=json.loads(settings.reference_config_path.read_text()) if settings.reference_scoring else None
        if settings.reference_scoring:
            for key in ['sample_spacing_m','reference_radius_m']:
                value=app.state.reference_config[key]
                if not math.isfinite(value) or value<=0:raise ValueError('Invalid reference-scoring configuration')
            value=app.state.reference_config['reference_margin_m']
            if not math.isfinite(value) or value<0:raise ValueError('Invalid reference ambiguity margin')
        logger.info('service_ready partition=%s bundle=%s trips=%d inference_enabled=%s',settings.partition,predictor.manifest['bundle_version'],len(store.trip_ids),settings.inference_enabled)
        yield
        logger.info('service_stopped')

    app=FastAPI(title='PathSnap API',version='0.1.0',lifespan=lifespan,description='Trip-ID inference with isolated aggregate reference scoring.')
    app.add_middleware(CORSMiddleware,allow_origins=list(settings.cors_origins),allow_credentials=False,allow_methods=['GET','POST'],allow_headers=['Content-Type','X-Request-ID'])

    @app.middleware('http')
    async def request_log(request,call_next):
        request.state.request_id=str(uuid4());start=time.perf_counter()
        try:response=await call_next(request)
        except Exception:
            logger.exception('request_failed request_id=%s',request.state.request_id)
            response=JSONResponse(status_code=500,content={'detail':'Internal server error','request_id':request.state.request_id})
        response.headers['X-Request-ID']=request.state.request_id
        logger.info('request request_id=%s method=%s path=%s status=%d duration_ms=%.2f',request.state.request_id,request.method,request.url.path,response.status_code,(time.perf_counter()-start)*1000)
        return response

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request,exception):
        return JSONResponse(status_code=exception.status_code,content={'detail':exception.detail,'request_id':request.state.request_id},headers=exception.headers)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request,exception):
        errors=[{key:error[key] for key in ['loc','msg','type']} for error in exception.errors()]
        return JSONResponse(status_code=422,content={'detail':errors,'request_id':request.state.request_id})

    async def health(status):
        return {'status':status,'bundle_version':app.state.predictor.manifest['bundle_version'],'partition':settings.partition,
                'inference_enabled':settings.inference_enabled,'reference_scoring_enabled':settings.reference_scoring}

    @app.get('/healthz',response_model=HealthResponse)
    async def healthz():return await health('ok')

    @app.get('/readyz',response_model=HealthResponse)
    async def readyz():return await health('ready')

    @app.get('/trips',response_model=TripsResponse)
    async def trips():return {'partition':settings.partition,'trip_ids':list(app.state.store.trip_ids),'inference_enabled':settings.inference_enabled}

    @app.post('/predict',response_model=PredictResponse)
    def predict(body:PredictRequest,request:Request):
        trip_id=body.trip_id;request_id=request.state.request_id
        if trip_id not in app.state.store.trip_ids:raise HTTPException(404,'Unknown trip ID')
        if not settings.inference_enabled:raise HTTPException(409,'Evaluator inference is disabled until the full system is frozen')
        if not app.state.predict_lock.acquire(blocking=False):raise HTTPException(503,'Prediction service busy; retry shortly',headers={'Retry-After':'1'})
        try:
            logger.info('inference_started request_id=%s trip_id=%s',request_id,trip_id)
            try:
                track,nodes,arcs=app.state.store.read_inputs(trip_id)
                prediction=app.state.predictor.predict(track,nodes,arcs)
            except Exception:
                logger.exception('inference_failed request_id=%s trip_id=%s',request_id,trip_id)
                raise HTTPException(503,'Prediction service unavailable; inspect server logs') from None
            logger.info('inference_complete request_id=%s trip_id=%s observations=%d',request_id,trip_id,len(prediction['observations']))
            evaluation=unavailable('disabled',len(track))
            if settings.reference_scoring:
                try:
                    logger.info('reference_scoring_started request_id=%s trip_id=%s',request_id,trip_id)
                    route=app.state.store.read_reference(trip_id)
                    evaluation=unavailable('reference_unavailable',len(track)) if route is None else scorer(track,nodes,arcs,route,prediction,app.state.reference_config)
                except Exception:
                    logger.exception('reference_scoring_failed request_id=%s trip_id=%s',request_id,trip_id)
                    evaluation=unavailable('invalid_reference',len(track))
            gps=[None if row is None else {'observation_id':i,'longitude':row[0],'latitude':row[1],'timestamp':row[2]} for i,row in enumerate(normalise_track(track))]
            return {'request_id':request_id,'trip_id':trip_id,'partition':settings.partition,'gps_observations':gps,'prediction':prediction,'evaluation':evaluation}
        finally:app.state.predict_lock.release()

    return app
