"""Explicit server settings; relative paths resolve from project root."""
from dataclasses import dataclass
import os
from pathlib import Path


def boolean(name,default):
    value=os.getenv(name,str(default)).lower()
    if value not in {'true','false','1','0'}:raise ValueError(f'{name} requires true/false')
    return value in {'true','1'}


@dataclass(frozen=True)
class Settings:
    bundle_dir:Path
    archive_path:Path
    registry_path:Path
    reference_config_path:Path
    partition:str='student_test'
    enable_evaluator_inference:bool=False
    reference_scoring:bool=True
    cors_origins:tuple=('http://localhost:8501','http://127.0.0.1:8501')

    @property
    def inference_enabled(self):return self.partition!='evaluator_test' or self.enable_evaluator_inference

    @classmethod
    def from_env(cls):
        root=Path(os.getenv('PATHSNAP_PROJECT_ROOT',Path.cwd())).resolve()
        def path(name,default):
            value=Path(os.getenv(name,str(default))).expanduser()
            return value.resolve() if value.is_absolute() else (root/value).resolve()
        partition=os.getenv('PATHSNAP_PARTITION','student_test')
        if partition not in {'student_test','evaluator_test'}:raise ValueError('Unsupported serving partition')
        archive='../Provided_Material/Student folder.zip' if partition=='student_test' else Path.home()/'Downloads/evaluator_test.zip'
        registry='configs/student_registry.json' if partition=='student_test' else 'configs/evaluator_registry.json'
        return cls(bundle_dir=path('PATHSNAP_BUNDLE_DIR','artifacts/releases/pathsnap-v0.1.1'),
                   archive_path=path('PATHSNAP_DATA_ARCHIVE',archive),registry_path=path('PATHSNAP_TRIP_REGISTRY',registry),
                   reference_config_path=path('PATHSNAP_REFERENCE_CONFIG','configs/preprocessing.json'),partition=partition,
                   enable_evaluator_inference=boolean('PATHSNAP_ENABLE_EVALUATOR_INFERENCE',False),
                   reference_scoring=boolean('PATHSNAP_REFERENCE_SCORING',True),
                   cors_origins=tuple(v.strip() for v in os.getenv('PATHSNAP_CORS_ORIGINS','http://localhost:8501,http://127.0.0.1:8501').split(',') if v.strip()))
