"""Export a self-contained, versioned classifier/preprocessing/HMM bundle."""
import argparse
from importlib import metadata
import json
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from packaging.requirements import Requirement
from pathsnap.inference.bundle import file_hash,load_bundle,PREPROCESSING_KEYS,HMM_KEYS

RUNTIME_FILES=(
    '__init__.py','features/__init__.py','features/candidates.py','features/spatial.py',
    'decoding/__init__.py','decoding/network.py','decoding/viterbi.py',
    'inference/__init__.py','inference/bundle.py','inference/pipeline.py','inference/io.py','inference/predict.py')
ROOT_DEPENDENCIES=('numpy','scipy','pyproj','scikit-learn','joblib','threadpoolctl')


def runtime_versions():
    versions={};pending=list(ROOT_DEPENDENCIES)
    while pending:
        name=pending.pop().lower().replace('_','-')
        if name in versions:continue
        versions[name]=metadata.version(name)
        for spec in metadata.requires(name) or []:
            dependency=Requirement(spec)
            if dependency.marker is None or dependency.marker.evaluate({'extra':''}):pending.append(dependency.name)
    return dict(sorted(versions.items()))


def export_bundle(project_root,model_path,output_root,version,*,model_config_path=None):
    project_root=Path(project_root).resolve();model_path=Path(model_path).resolve();output_root=Path(output_root).resolve()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}',version):raise ValueError('Invalid bundle version')
    name='pathsnap-'+version;destination=output_root/name;archive=output_root/(name+'.zip')
    if destination.exists() or archive.exists():raise FileExistsError('Release already exists; choose a new version')
    config_root=project_root/'configs'
    preprocessing=json.loads((config_root/'preprocessing.json').read_text());hmm=json.loads((config_root/'hmm.json').read_text())
    selected=json.loads(Path(model_config_path or config_root/'tuned_model.json').read_text())
    if not model_path.is_file():raise FileNotFoundError('Regenerate the Step 7 tuned model before exporting')
    output_root.mkdir(parents=True,exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix='.'+name+'-',dir=output_root));zip_tmp=stage.parent/(stage.name+'.zip')
    versions=runtime_versions()
    try:
        (stage/'configs').mkdir()
        shutil.copy2(model_path,stage/'model.joblib')
        for source,filename,keys in [(preprocessing,'preprocessing.json',PREPROCESSING_KEYS),(hmm,'hmm.json',HMM_KEYS)]:
            (stage/'configs'/filename).write_text(json.dumps({k:source[k] for k in keys},indent=2)+'\n')
        model_config={k:selected[k] for k in ['model_name','model_parameters','feature_columns','positive_class']}
        (stage/'configs/model.json').write_text(json.dumps(model_config,indent=2)+'\n')
        for filename in RUNTIME_FILES:
            target=stage/'pathsnap'/filename;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(project_root/'src/pathsnap'/filename,target)
        launcher='''from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from pathsnap.inference.predict import main
if __name__ == "__main__":
    main()
'''
        (stage/'run_inference.py').write_text(launcher)
        (stage/'requirements.txt').write_text('# Exact runtime dependency closure from the verified export environment.\n'+''.join(f'{name}=={version}\n' for name,version in versions.items()))
        readme=f'''# PathSnap inference bundle {version}

Exported and verified with Python {platform.python_version()} on {platform.system()}.
Use Python {sys.version_info.major}.{sys.version_info.minor} and install the pinned runtime requirements.
The loader rejects different Python minor versions or package versions before loading weights.

From this extracted directory, create/activate a virtual environment, then:

```bash
python -m pip install -r requirements.txt
python run_inference.py --bundle . --trip-dir /path/to/00000007 --output prediction.json
```

Input folder requires only 00000007.track, 00000007.nodes and 00000007.arcs.
File columns are longitude/latitude/timestamp, longitude/latitude, and integer from/to node IDs.
No .route file is opened. No dataset, reference labels, evaluation reports or trip registry is included.
The original PathSnap repository is not needed to run this bundle.

The output has one entry per original GPS row, selected road IDs, explicit resets and separate
route parts with GeoJSON MultiLineString geometry. No accuracy or reference labels are returned.
Invalid GPS rows are retained as null predictions; invalid road geometry is rejected.

Model: selected tuned Random Forest. Features are unscaled; there is no learned scaler to export.
Preprocessing and HMM settings are frozen. No optimisation or model training runs during inference.
Road networks are supplied per trip and are not globally baked into the model.

Only load trusted bundles: joblib/pickle can execute code. File checksums detect corruption,
not the authenticity of a modified manifest. Manifest code/config hashes bind this exact snapshot;
base_git_revision records its parent source revision, not a claim that pending export code was
already committed there. Compatible wheels must be available for the target OS/environment.
'''
        (stage/'README.md').write_text(readme)
        revision=subprocess.run(['git','rev-parse','HEAD'],cwd=project_root,capture_output=True,text=True,check=True).stdout.strip()
        manifest={'schema_version':1,'bundle_version':version,'python_major_minor':list(sys.version_info[:2]),
                  'python_version':platform.python_version(),'tested_platform':platform.platform(),
                  'runtime_versions':versions,'model_type':'sklearn.ensemble.RandomForestClassifier',
                  'learned_preprocessing':'none; unscaled candidate features','base_git_revision':revision,
                  'reference_data_included':False,'runtime_input_types':['track','nodes','arcs'],
                  'files':{str(p.relative_to(stage)):file_hash(p) for p in sorted(stage.rglob('*')) if p.is_file()}}
        (stage/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
        load_bundle(stage)
        with zipfile.ZipFile(zip_tmp,'w',zipfile.ZIP_DEFLATED) as z:
            for path in sorted(stage.rglob('*')):
                if path.is_file():z.write(path,name+'/'+str(path.relative_to(stage)))
        with zipfile.ZipFile(zip_tmp) as z:
            if z.testzip() is not None:raise ValueError('Archive verification failed')
        stage.rename(destination);zip_tmp.rename(archive)
        return destination,archive,manifest
    finally:
        if stage.exists():shutil.rmtree(stage)
        if zip_tmp.exists():zip_tmp.unlink()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version',default='v0.1.0')
    parser.add_argument('--model',type=Path,default=Path('artifacts/bayesian_optimization/tuned.joblib'))
    parser.add_argument('--output-root',type=Path,default=Path('artifacts/releases'))
    parser.add_argument('--report',type=Path,default=Path('results/experiments/inference_export/export.json'))
    args=parser.parse_args();directory,archive,manifest=export_bundle(Path.cwd(),args.model,args.output_root,args.version)
    report={'bundle_version':args.version,'bundle_directory':str(args.output_root/directory.name),'archive':str(args.output_root/archive.name),
            'archive_bytes':archive.stat().st_size,'archive_sha256':file_hash(archive),'model_sha256':manifest['files']['model.joblib'],
            'runtime_versions':manifest['runtime_versions'],'python_version':manifest['python_version'],
            'reference_data_included':False,'base_git_revision':manifest['base_git_revision']}
    args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
