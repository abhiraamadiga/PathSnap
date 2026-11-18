"""Directed metric routing while retaining original node/arc identifiers."""
from collections import OrderedDict
import numpy as np
from pyproj import CRS,Transformer
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra


class RoadNetwork:
    def __init__(self,nodes,arcs,max_distance_m=5000,cache_sources=128):
        coordinates=np.asarray(nodes,dtype=float);self.arcs=np.asarray(arcs,dtype=int)
        if coordinates.ndim!=2 or coordinates.shape[1]!=2 or not len(coordinates) or not np.isfinite(coordinates).all():
            raise ValueError('Invalid nodes')
        if self.arcs.ndim!=2 or self.arcs.shape[1]!=2 or not len(self.arcs) or self.arcs.min()<0 or self.arcs.max()>=len(coordinates):
            raise ValueError('Invalid arcs')
        if not np.isfinite(max_distance_m) or max_distance_m<=0 or cache_sources<1:raise ValueError('Invalid routing limits')
        lon,lat=coordinates[0]
        crs=CRS.from_proj4(f'+proj=aeqd +lat_0={lat} +lon_0={lon} +datum=WGS84 +units=m')
        self.transformer=Transformer.from_crs('EPSG:4326',crs,always_xy=True)
        self.xy=self.project(coordinates)
        if not np.isfinite(self.xy).all():raise ValueError('Projection produced invalid coordinates')
        self.lengths=np.linalg.norm(self.xy[self.arcs[:,1]]-self.xy[self.arcs[:,0]],axis=1)
        self.max_distance=max_distance_m;self.cache_sources=cache_sources;self.cache=OrderedDict()
        # CSR duplicate entries would sum weights: explicitly retain the shortest
        # representative edge instead. Candidate state IDs are never deduplicated.
        self.edge_ids={}
        for arc_id,(u,v) in enumerate(self.arcs):
            key=(int(u),int(v));old=self.edge_ids.get(key)
            if old is None or (self.lengths[arc_id],arc_id)<(self.lengths[old],old):self.edge_ids[key]=arc_id
        keys=list(self.edge_ids)
        self.graph=csr_matrix(([self.lengths[self.edge_ids[k]] for k in keys],
                               ([k[0] for k in keys],[k[1] for k in keys])),shape=(len(nodes),len(nodes)))
        self.routing_queries=0

    def project(self,coordinates):
        coordinates=np.asarray(coordinates,dtype=float)
        x,y=self.transformer.transform(coordinates[:,0],coordinates[:,1]);return np.column_stack((x,y))

    def distances_from(self,source):
        source=int(source)
        if source in self.cache:
            value=self.cache.pop(source);self.cache[source]=value;return value
        value=dijkstra(self.graph,directed=True,indices=source,return_predecessors=True,limit=self.max_distance)
        self.routing_queries+=1;self.cache[source]=value
        if len(self.cache)>self.cache_sources:self.cache.popitem(last=False)
        return value

    def connector(self,source,target):
        source,target=int(source),int(target)
        if source==target:return []
        distances,predecessors=self.distances_from(source)
        if not np.isfinite(distances[target]):return None
        path=[];node=target
        for _ in range(len(self.xy)):
            previous=int(predecessors[node])
            if previous<0:return None
            path.append(self.edge_ids[(previous,node)]);node=previous
            if node==source:return list(reversed(path))
        raise RuntimeError('Routing predecessor cycle')

    def distance_matrix(self,previous,current,backward_tolerance_m):
        """Distances between snapped directed candidate positions; no labels."""
        ids=np.asarray([c['arc_id'] for c in current],dtype=int)
        fractions=np.asarray([c['projection_fraction'] for c in current],dtype=float)
        matrix=np.full((len(previous),len(current)),np.inf)
        for i,candidate in enumerate(previous):
            a=candidate['arc_id'];fraction=candidate['projection_fraction']
            distances,_=self.distances_from(self.arcs[a,1])
            matrix[i]=(1-fraction)*self.lengths[a]+distances[self.arcs[ids,0]]+fractions*self.lengths[ids]
            same=ids==a;delta=(fractions-fraction)*self.lengths[a]
            forward_or_jitter=same & (delta>=-backward_tolerance_m)
            matrix[i,forward_or_jitter]=np.maximum(0,delta[forward_or_jitter])
        matrix[matrix>self.max_distance]=np.inf
        return matrix
