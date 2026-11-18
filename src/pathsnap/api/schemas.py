"""Public schemas deliberately exclude reference routes and per-observation labels."""
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field


class PredictRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    trip_id:str=Field(pattern=r'^[0-9]{8}$')


class Observation(BaseModel):
    observation_id:int
    status:str
    candidate_count:int
    classifier_arc_id:int|None
    predicted_arc_id:int|None
    segment_id:int|None
    reset_reason:str|None


class Geometry(BaseModel):
    type:Literal['MultiLineString']
    coordinates:list[list[list[float]]]


class RoutePart(BaseModel):
    arc_ids:list[int]
    geometry:Geometry


class Prediction(BaseModel):
    schema_version:int
    bundle_version:str
    observations:list[Observation]
    route_parts:list[RoutePart]
    diagnostics:dict[str,int]
    prediction_seconds:float


class Evaluation(BaseModel):
    status:Literal['ok','disabled','reference_unavailable','invalid_reference']
    total_observations:int
    evaluated_observations:int|None=None
    abstained_observations:int|None=None
    reference_coverage:float|None=None
    hmm_weak_reference_top1:float|None=None
    classifier_weak_reference_top1:float|None=None
    reference_sequence_edit_similarity:float|None=None
    reference_arc_set_f1:float|None=None
    note:str


class GPSPoint(BaseModel):
    observation_id:int
    longitude:float
    latitude:float
    timestamp:float


class PredictResponse(BaseModel):
    request_id:str
    trip_id:str
    partition:Literal['student_test','evaluator_test']
    gps_observations:list[GPSPoint|None]
    prediction:Prediction
    evaluation:Evaluation


class HealthResponse(BaseModel):
    status:Literal['ok','ready']
    bundle_version:str
    partition:str
    inference_enabled:bool
    reference_scoring_enabled:bool


class TripsResponse(BaseModel):
    partition:str
    trip_ids:list[str]
    inference_enabled:bool
