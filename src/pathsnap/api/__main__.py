"""Start one API worker; the model bundle is loaded once at startup."""
import argparse
import os
import uvicorn


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host',default=os.getenv('PATHSNAP_API_HOST','0.0.0.0'))
    parser.add_argument('--port',type=int,default=int(os.getenv('PATHSNAP_API_PORT','8000')))
    args=parser.parse_args();uvicorn.run('pathsnap.api.app:create_app',factory=True,host=args.host,port=args.port,workers=1)


if __name__=='__main__':main()
