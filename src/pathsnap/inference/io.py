"""Trip directory reader that never opens .route files."""
from pathlib import Path


def read_inputs(folder):
    folder=Path(folder);trip_id=folder.name;result={}
    for kind,width,convert in [('track',3,float),('nodes',2,float),('arcs',2,int)]:
        path=folder/f'{trip_id}.{kind}';rows=[]
        for i,line in enumerate(path.read_text(encoding='utf-8-sig').splitlines()):
            try:
                values=line.split()
                if len(values)!=width:raise ValueError('column count')
                rows.append(tuple(convert(v) for v in values))
            except ValueError:
                if kind=='track':rows.append(None)
                else:raise ValueError(f'Invalid {kind} row {i}') from None
        result[kind]=rows
    return result['track'],result['nodes'],result['arcs']
