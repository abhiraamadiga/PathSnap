"""Load trusted local bundles after integrity/environment/schema checks."""
import hashlib
from importlib import metadata
import json
import math
from pathlib import Path
import sys

PREPROCESSING_KEYS=('candidate_radius_m','max_candidates','sample_spacing_m','gap_reset_s')
RUNTIME_DEPENDENCIES=('numpy','scipy','pyproj','scikit-learn','joblib','threadpoolctl')
HMM_KEYS=('beta_m','gap_reset_s','max_speed_m_s','transition_noise_m','backward_tolerance_m','max_route_distance_m','routing_cache_sources','emission_epsilon')


def file_hash(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def verify_bundle(directory):
    root=Path(directory).resolve();manifest=json.loads((root/'manifest.json').read_text())
    if manifest.get('schema_version')!=1:raise ValueError('Unsupported bundle schema')
    if manifest.get('reference_data_included') is not False:raise ValueError('Bundle must exclude reference data')
    if not set(RUNTIME_DEPENDENCIES)<=set(manifest['runtime_versions']):raise ValueError('Missing runtime version pins')
    required={'model.joblib','configs/preprocessing.json','configs/hmm.json','configs/model.json','requirements.txt','run_inference.py'}
    if not required<=set(manifest['files']):raise ValueError('Bundle missing required file entries')
    for name,expected in manifest['files'].items():
        path=(root/name).resolve()
        if not path.is_relative_to(root) or not path.is_file():raise ValueError(f'Missing/invalid bundle path: {name}')
        if file_hash(path)!=expected:raise ValueError(f'Bundle checksum mismatch: {name}')
    if list(sys.version_info[:2])!=manifest['python_major_minor']:
        raise ValueError(f"Bundle requires Python {'.'.join(map(str,manifest['python_major_minor']))}; use the recorded environment")
    for name,expected in manifest['runtime_versions'].items():
        try:actual=metadata.version(name)
        except metadata.PackageNotFoundError:raise ValueError(f'Install bundle requirements: missing {name}') from None
        if actual!=expected:raise ValueError(f'Install bundle requirements: {name} expected {expected}, found {actual}')
    return manifest


def load_bundle(directory):
    root=Path(directory);manifest=verify_bundle(root)
    import joblib
    from pathsnap.features.candidates import FEATURES
    from pathsnap.inference.pipeline import Predictor
    preprocessing=json.loads((root/'configs/preprocessing.json').read_text());hmm=json.loads((root/'configs/hmm.json').read_text())
    model_config=json.loads((root/'configs/model.json').read_text())
    if set(preprocessing)!=set(PREPROCESSING_KEYS) or set(hmm)!=set(HMM_KEYS):raise ValueError('Unexpected runtime configuration keys')
    if model_config['feature_columns']!=FEATURES or preprocessing['gap_reset_s']!=hmm['gap_reset_s']:raise ValueError('Feature order/reset mismatch')
    for key in ['candidate_radius_m','sample_spacing_m','gap_reset_s']:
        if not math.isfinite(preprocessing[key]) or preprocessing[key]<=0:raise ValueError('Invalid preprocessing setting')
    for key in ['beta_m','gap_reset_s','max_speed_m_s','max_route_distance_m']:
        if not math.isfinite(hmm[key]) or hmm[key]<=0:raise ValueError('Invalid HMM setting')
    for key in ['transition_noise_m','backward_tolerance_m']:
        if not math.isfinite(hmm[key]) or hmm[key]<0:raise ValueError('Invalid HMM tolerance')
    if not 0<hmm['emission_epsilon']<=1 or not isinstance(hmm['routing_cache_sources'],int) or hmm['routing_cache_sources']<1:raise ValueError('Invalid HMM numerical/cache setting')
    if not isinstance(preprocessing['max_candidates'],int) or preprocessing['max_candidates']<1:raise ValueError('Invalid candidate count')
    if model_config['positive_class']!=1 or model_config['model_parameters']['n_jobs']<1:raise ValueError('Invalid class/thread setting')
    model=joblib.load(root/'model.joblib')
    if model.n_features_in_!=len(FEATURES) or model_config['positive_class'] not in model.classes_:raise ValueError('Model feature/class mismatch')
    for name,value in model_config['model_parameters'].items():
        if model.get_params()[name]!=value:raise ValueError('Model parameter mismatch')
    return Predictor(model,preprocessing,hmm,model_config,manifest)
