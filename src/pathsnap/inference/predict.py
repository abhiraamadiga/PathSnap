"""Run exported inference on a local GPS/road trip directory."""
import argparse
import json
from pathlib import Path
from pathsnap.inference.bundle import load_bundle
from pathsnap.inference.io import read_inputs


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--trip-dir',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    predictor=load_bundle(args.bundle)
    result=predictor.predict(*read_inputs(args.trip_dir))
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,allow_nan=False)+'\n')
    print(json.dumps({'bundle_version':result['bundle_version'],**result['diagnostics'],'prediction_seconds':result['prediction_seconds']},indent=2))


if __name__=='__main__':main()
