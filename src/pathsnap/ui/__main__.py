"""Start the evaluator UI on Laptop 2; no ML packages are required here."""
import argparse
import os
from pathlib import Path
from pathsnap.ui.server import serve


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host',default=os.getenv('PATHSNAP_UI_HOST','0.0.0.0'))
    parser.add_argument('--port',type=int,default=int(os.getenv('PATHSNAP_UI_PORT','8501')))
    parser.add_argument('--api-url',default=os.getenv('PATHSNAP_API_URL','http://localhost:8000'))
    parser.add_argument('--directory',type=Path,default=Path(os.getenv('PATHSNAP_PROJECT_ROOT',Path.cwd()))/'ui')
    args=parser.parse_args();serve(args.directory,args.api_url,args.host,args.port)


if __name__=='__main__':main()
