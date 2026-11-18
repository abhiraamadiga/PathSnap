"""Verify an exported bundle independently against ten development-trip snapshots."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile


def digest(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle-zip',type=Path,required=True)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--expected',type=Path,default=Path('results/experiments/hmm_viterbi'))
    parser.add_argument('--report',type=Path,default=Path('results/experiments/inference_export/verification.json'))
    args=parser.parse_args();baseline=json.loads((args.expected/'manifest.json').read_text())
    if digest(args.source)!=baseline['raw_development_sha256']:raise ValueError('Original development ZIP required; evaluator archive excluded')
    trips=sorted({r['trip_id'] for r in csv.DictReader((args.expected/'comparison.csv').open())})
    if len(trips)!=10:raise ValueError('Expected ten student-development snapshots')
    results=[]
    with tempfile.TemporaryDirectory(prefix='pathsnap-standalone-') as tmp:
        work=Path(tmp)
        with zipfile.ZipFile(args.bundle_zip) as archive:
            for member in archive.infolist():
                path=(work/member.filename).resolve()
                if not path.is_relative_to(work):raise ValueError('Unsafe archive member')
                if not member.is_dir():path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(archive.read(member))
        roots=[p.parent for p in work.glob('*/manifest.json')]
        if len(roots)!=1:raise ValueError('Expected one versioned bundle root')
        bundle=roots[0]
        # Isolated Python ignores PYTHONPATH and imports the copied runtime snapshot.
        probe='import sys; from pathlib import Path; sys.path.insert(0,sys.argv[1]); import pathsnap; assert Path(pathsnap.__file__).resolve().is_relative_to(Path(sys.argv[1])); print(pathsnap.__file__)'
        subprocess.run([sys.executable,'-I','-c',probe,str(bundle)],cwd=work,check=True,capture_output=True,text=True)
        with zipfile.ZipFile(args.source) as source:
            for trip_id in trips:
                folder=work/'inputs'/trip_id;folder.mkdir(parents=True)
                for kind in ['track','nodes','arcs']:
                    name=f'{trip_id}.{kind}'
                    (folder/name).write_bytes(source.read(f'Student folder/student_test/{trip_id}/{name}'))
                assert not list(folder.glob('*.route'))
                output=work/f'{trip_id}.json'
                completed=subprocess.run([sys.executable,'-I',str(bundle/'run_inference.py'),'--bundle',str(bundle),'--trip-dir',str(folder),'--output',str(output)],
                                         cwd=work,check=True,capture_output=True,text=True)
                prediction=json.loads(output.read_text());expected=list(csv.DictReader((args.expected/f'{trip_id}_predictions.csv').open()))
                if len(prediction['observations'])!=len(expected):raise ValueError('Observation count mismatch')
                for row,old in zip(prediction['observations'],expected):
                    if row['observation_id']!=int(old['observation_id']):raise ValueError('Observation ID mismatch')
                    for new_key,old_key in [('classifier_arc_id','classifier_arc'),('predicted_arc_id','hmm_arc')]:
                        wanted=int(old[old_key]) if old[old_key] else None
                        if row[new_key]!=wanted:raise ValueError(f'{trip_id}: prediction differs at {row["observation_id"]}')
                prior=json.loads((args.expected/f'{trip_id}_routes.json').read_text())
                if [p['arc_ids'] for p in prediction['route_parts']]!=prior['hmm_parts']:raise ValueError('Route part mismatch')
                if 'accuracy' in prediction or 'weak_reference_arc' in json.dumps(prediction):raise ValueError('Scoring leaked into inference output')
                results.append({'trip_id':trip_id,'observations':len(expected),'predictions_match_step8':True,
                                'route_parts_match_step8':True,'prediction_seconds':prediction['prediction_seconds']})
                print(f'{trip_id}: {len(expected)} observations and route parts match',flush=True)
    report={'archive_sha256':digest(args.bundle_zip),'verification_mode':'isolated Python subprocess per trip; no original repository imports',
            'raw_input_types':['track','nodes','arcs'],'reference_files_present':False,
            'trips':results,'total_observations':sum(r['observations'] for r in results),'all_predictions_match':True,'all_route_parts_match':True}
    args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='trips'},indent=2))


if __name__=='__main__':main()
