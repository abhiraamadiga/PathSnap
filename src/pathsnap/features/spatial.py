"""Metric road projection and radius-complete spatial candidate lookup."""
import numpy as np
from pyproj import CRS, Transformer
from scipy.spatial import cKDTree


class RoadIndex:
    def __init__(self, nodes, arcs, spacing_m=50.0):
        if spacing_m <= 0:
            raise ValueError('spacing_m must be positive')
        lonlat = np.asarray(nodes, dtype=float)
        arcs = np.asarray(arcs, dtype=int)
        if lonlat.ndim != 2 or lonlat.shape[1] != 2 or not np.isfinite(lonlat).all():
            raise ValueError('Invalid node coordinates')
        if arcs.ndim != 2 or arcs.shape[1] != 2 or not len(arcs) or arcs.min() < 0 or arcs.max() >= len(nodes):
            raise ValueError('Invalid arc references')
        lon, lat = lonlat[0]
        local = CRS.from_proj4(f'+proj=aeqd +lat_0={lat} +lon_0={lon} +datum=WGS84 +units=m')
        self.transformer = Transformer.from_crs('EPSG:4326', local, always_xy=True)
        self.xy = self.project(lonlat)
        self.start, self.end = self.xy[arcs[:, 0]], self.xy[arcs[:, 1]]
        self.vector = self.end-self.start
        self.length = np.linalg.norm(self.vector, axis=1)
        self.spacing = spacing_m
        # Endpoints plus interior samples; every segment location is within spacing/2
        # of a sample. The enlarged search radius therefore cannot miss an arc in radius.
        counts = np.maximum(1, np.ceil(self.length/spacing_m).astype(int))
        samples, ids = [], []
        for arc_id, count in enumerate(counts):
            fraction = np.linspace(0, 1, count+1)
            samples.append(self.start[arc_id]+fraction[:, None]*self.vector[arc_id])
            ids.append(np.full(count+1, arc_id))
        self.sample_ids = np.concatenate(ids)
        self.tree = cKDTree(np.concatenate(samples))

    def project(self, lonlat):
        coords = np.asarray(lonlat, dtype=float)
        x, y = self.transformer.transform(coords[:, 0], coords[:, 1])
        return np.column_stack((x,y))

    def distances(self, point, arc_ids):
        arc_ids = np.asarray(arc_ids, dtype=int)
        vector = self.vector[arc_ids]
        length2 = np.einsum('ij,ij->i', vector, vector)
        fraction = np.divide(np.einsum('ij,ij->i', point-self.start[arc_ids], vector), length2,
                             out=np.zeros(len(arc_ids)), where=length2>0)
        fraction = np.clip(fraction, 0, 1)
        projected = self.start[arc_ids]+fraction[:, None]*vector
        return np.linalg.norm(projected-point, axis=1), fraction

    def candidates(self, point, radius_m=75.0, limit=8):
        if radius_m <= 0 or limit < 1:
            raise ValueError('Invalid radius or candidate limit')
        hits = self.tree.query_ball_point(point, radius_m+self.spacing/2+1e-8)
        ids = np.unique(self.sample_ids[hits])
        distance, fraction = self.distances(point, ids)
        keep = np.flatnonzero(distance <= radius_m)
        order = keep[np.lexsort((ids[keep], distance[keep]))][:limit]
        return [(int(ids[i]), float(distance[i]), float(fraction[i])) for i in order]
