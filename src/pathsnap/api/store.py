"""Server-owned ZIP reads: prediction inputs and private references are separate."""
import hashlib
import json
from pathlib import Path
import re
import zipfile


class TripStore:
    def __init__(self,archive,registry_path,partition):
        self.archive=Path(archive);registry=json.loads(Path(registry_path).read_text())
        if registry['partition']!=partition:raise ValueError('Partition/registry mismatch')
        ids=registry['trip_ids']
        if len(ids)!=10 or len(set(ids))!=10 or any(re.fullmatch(r'[0-9]{8}',i) is None for i in ids):raise ValueError('Expected ten unique eight-digit trip IDs')
        with self.archive.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
        if digest!=registry['archive_sha256']:raise ValueError('Archive checksum mismatch')
        self.trip_ids=tuple(sorted(ids));self.partition=partition
        self.prefix='Student folder/student_test' if partition=='student_test' else 'evaluator_test'
        with zipfile.ZipFile(self.archive) as archive:
            names=archive.namelist()
            if len(names)!=len(set(names)):raise ValueError('Duplicate archive members')
            self.names=frozenset(names)
        for trip_id in self.trip_ids:
            for kind in ['track','nodes','arcs']:
                if self.member(trip_id,kind) not in self.names:raise ValueError('Missing inference input file')
        stat=self.archive.stat();self.stamp=(stat.st_size,stat.st_mtime_ns)

    def member(self,trip_id,kind):
        if trip_id not in self.trip_ids:raise KeyError('Unknown trip ID')
        if kind not in {'track','nodes','arcs','route'}:raise ValueError('Unsupported file type')
        return f'{self.prefix}/{trip_id}/{trip_id}.{kind}'

    def read(self,trip_id,kind):
        member=self.member(trip_id,kind)
        stat=self.archive.stat()
        if (stat.st_size,stat.st_mtime_ns)!=self.stamp:raise OSError('Dataset changed; restart service')
        if member not in self.names:return None
        with zipfile.ZipFile(self.archive) as archive:return archive.read(member).decode('utf-8-sig')

    def read_inputs(self,trip_id):
        result=[]
        for kind,width,convert in [('track',3,float),('nodes',2,float),('arcs',2,int)]:
            raw=self.read(trip_id,kind)
            if raw is None:raise FileNotFoundError('Missing prediction input')
            rows=[]
            for line in raw.splitlines():
                try:
                    values=line.split()
                    if len(values)!=width:raise ValueError('Invalid columns')
                    rows.append(tuple(convert(v) for v in values))
                except ValueError:
                    if kind=='track':rows.append(None)
                    else:raise ValueError('Invalid road input row') from None
            result.append(rows)
        return tuple(result)

    def read_reference(self,trip_id):
        raw=self.read(trip_id,'route')
        if raw is None:return None
        rows=[]
        for line in raw.splitlines():
            values=line.split()
            if len(values)!=1:raise ValueError('Invalid reference row')
            try:rows.append((int(values[0]),))
            except ValueError:raise ValueError('Invalid reference value') from None
        return rows
