import unittest
from pathsnap.features.spatial import RoadIndex
from pathsnap.features.preprocessing import prepare,align_reference

CONFIG=dict(candidate_radius_m=75,max_candidates=8,sample_spacing_m=50,gap_reset_s=60)

class PreprocessingTests(unittest.TestCase):
    def test_long_segment_interior_is_found(self):
        index=RoadIndex([(0,0),(.1,0)],[(0,1)])
        point=index.project([(.05,.0001)])[0]
        result=index.candidates(point)
        self.assertEqual(result[0][0],0)
        self.assertAlmostEqual(result[0][1],11.06,delta=.2)
        self.assertAlmostEqual(result[0][2],.5,places=4)

    def test_top_k_radius_and_duplicate_ids(self):
        index=RoadIndex([(0,0),(.001,0),(.001,.001)],[(0,1),(0,1),(2,2)])
        point=index.project([(.0005,0)])[0]
        self.assertEqual([r[0] for r in index.candidates(point,10,8)],[0,1])
        self.assertEqual(len(index.candidates(point,10,1)),1)
        self.assertEqual(index.candidates(index.project([(1,1)])[0]),[])

    def test_invalid_gaps_and_heading(self):
        _,rows=prepare([(0,0,1),(.0001,0,2),(.0002,0,100),None,(0,0,101)],
                       [(0,0),(.001,0)],[(0,1)],CONFIG)
        self.assertEqual(len(rows),5)
        self.assertEqual(rows[1]['candidates'][0]['heading_available'],1)
        self.assertEqual(rows[2]['candidates'][0]['gap_reset'],1)
        self.assertEqual(rows[3]['status'],'invalid_observation')
        self.assertEqual(rows[4]['candidates'][0]['gap_reset'],1)

    def test_weak_label_ambiguity_and_distance_abstention(self):
        index=RoadIndex([(0,0),(.001,0)],[(0,1),(1,0)])
        self.assertEqual(align_reference([(.0005,0,1)],index,[(0,),(1,)])[0]['reason'],'ambiguous_reference')
        labels=align_reference([(.0005,0,1),(1,1,2)],index,[(0,)])
        self.assertEqual(labels[0]['arc_id'],0)
        self.assertEqual(labels[1]['reason'],'reference_too_far')

    def test_reference_changes_do_not_change_features(self):
        track=[(.0005,0,1)]; nodes=[(0,0),(.001,0)]; arcs=[(0,1),(1,0)]
        index,first=prepare(track,nodes,arcs,CONFIG)
        align_reference(track,index,[(0,)])
        align_reference(track,index,[(1,)])
        _,second=prepare(track,nodes,arcs,CONFIG)
        self.assertEqual(first,second)

    def test_index_matches_brute_force_radius(self):
        import numpy as np
        rng=np.random.default_rng(7)
        nodes=rng.uniform(-.005,.005,(30,2))
        arcs=rng.integers(0,30,(50,2))
        index=RoadIndex(nodes,arcs)
        ids=np.arange(50)
        for coordinates in rng.uniform(-.005,.005,(10,2)):
            point=index.project([coordinates])[0]
            distances,_=index.distances(point,ids)
            expected=sorted((int(i) for i in ids if distances[i]<=75),key=lambda i:(distances[i],i))
            actual=[r[0] for r in index.candidates(point,75,50)]
            self.assertEqual(actual,expected)
