import unittest
import numpy as np
from pathsnap.decoding.network import RoadNetwork
from pathsnap.decoding.viterbi import decode,prepare_sequence,reconstruct_route

CFG=dict(gap_reset_s=60,max_speed_m_s=80,transition_noise_m=150,backward_tolerance_m=20,emission_epsilon=1e-9)

def row(i,ids,fraction=.5):
    return {'observation_id':i,'candidates':[{'arc_id':a,'projection_fraction':fraction} for a in ids]}


class ViterbiTests(unittest.TestCase):
    def test_directed_routing_keeps_ids_and_does_not_sum_duplicates(self):
        network=RoadNetwork([(0,0),(.001,0),(.002,0)],[(0,1),(0,1),(1,2)])
        self.assertEqual(network.connector(0,2),[0,2])
        self.assertIsNone(network.connector(2,0))
        self.assertAlmostEqual(network.distances_from(0)[0][1],111.319,delta=.1)
        self.assertEqual(network.connector(1,1),[])

    def test_long_connector_is_reconstructed(self):
        network=RoadNetwork([(0,0),(.001,0),(.002,0),(.003,0)],[(0,1),(1,2),(2,3)])
        observations=[row(0,[0]),row(1,[2])]
        steps=prepare_sequence(observations,[[1],[1]],[(.0005,0,1),(.0025,0,5)],network,CFG)
        result=decode(steps,50)
        self.assertEqual(reconstruct_route(observations,result,steps,network,CFG),[[0,1,2]])

    def test_disconnected_predictions_restart_without_fake_connector(self):
        network=RoadNetwork([(0,0),(.001,0),(.002,0),(.003,0)],[(0,1),(2,3)])
        observations=[row(0,[0]),row(1,[1])]
        steps=prepare_sequence(observations,[[1],[1]],[(.0005,0,1),(.0025,0,2)],network,CFG)
        result=decode(steps,50)
        self.assertEqual(result[1]['reset_reason'],'no_valid_transition')
        self.assertNotEqual(result[0]['segment_id'],result[1]['segment_id'])
        self.assertEqual(reconstruct_route(observations,result,steps,network,CFG),[[0],[1]])

    def test_gap_missing_and_invalid_gps_preserve_observations(self):
        network=RoadNetwork([(0,0),(.001,0)],[(0,1)])
        observations=[row(0,[0]),row(1,[]),row(2,[0]),row(3,[0])]
        track=[(.0005,0,1),None,(.0005,0,2),(.0005,0,100)]
        steps=prepare_sequence(observations,[[0],[],[.5],[.5]],track,network,CFG)
        result=decode(steps,50)
        self.assertEqual(len(result),4);self.assertIsNone(result[1]['predicted_arc'])
        self.assertEqual(result[2]['reset_reason'],'after_missing_candidates')
        self.assertEqual(result[3]['reset_reason'],'gps_gap')
        self.assertTrue(np.isfinite(steps[0]['emission']).all())

    def test_viterbi_uses_future_evidence_and_backtracks(self):
        steps=[dict(ids=[10,20],emission=np.log([.4,.6]),reset_reason='start',distances=None,displacement_m=0),
               dict(ids=[11,21],emission=np.log([.99,.01]),reset_reason=None,distances=np.array([[0,np.inf],[np.inf,0]]),displacement_m=0)]
        result=decode(steps,50)
        self.assertEqual([r['predicted_arc'] for r in result],[10,11])

    def test_bounded_route_and_zero_length_arc(self):
        network=RoadNetwork([(0,0),(.001,0),(.002,0)],[(0,0),(0,1),(1,2)],max_distance_m=150)
        self.assertEqual(network.connector(0,1),[1]);self.assertIsNone(network.connector(0,2))
        distances=network.distance_matrix([{'arc_id':0,'projection_fraction':0}],[{'arc_id':0,'projection_fraction':0}],20)
        self.assertEqual(distances[0,0],0)

    def test_backward_jitter_and_larger_reversal(self):
        network=RoadNetwork([(0,0),(.001,0)],[(0,1)])
        previous=[{'arc_id':0,'projection_fraction':.8}]
        current=[{'arc_id':0,'projection_fraction':.7},{'arc_id':0,'projection_fraction':.1}]
        distances=network.distance_matrix(previous,current,20)
        self.assertEqual(distances[0,0],0);self.assertTrue(np.isinf(distances[0,1]))
        loop=RoadNetwork([(0,0),(.001,0)],[(0,1),(1,0)])
        self.assertAlmostEqual(loop.distance_matrix(previous,current,20)[0,1],1.3*loop.lengths[0],places=5)

    def test_invalid_probabilities_are_errors(self):
        network=RoadNetwork([(0,0),(.001,0)],[(0,1)])
        for p in [float('nan'),-.1,1.1]:
            with self.assertRaises(ValueError):prepare_sequence([row(0,[0])],[[p]],[(0,0,1)],network,CFG)

    def test_decoding_matches_exhaustive_path_search(self):
        import itertools
        from scipy.special import logsumexp
        steps=[dict(ids=[0,1],emission=np.log([.3,.7]),reset_reason='start',distances=None,displacement_m=0),
               dict(ids=[2,3],emission=np.log([.8,.2]),reset_reason=None,distances=np.array([[3,20],[15,2]]),displacement_m=4),
               dict(ids=[4,5],emission=np.log([.2,.8]),reset_reason=None,distances=np.array([[2,5],[8,3]]),displacement_m=4)]
        scores=[]
        for path in itertools.product(range(2),repeat=3):
            total=-np.log(2)+steps[0]['emission'][path[0]]
            for i in [1,2]:
                raw=-np.abs(steps[i]['distances']-steps[i]['displacement_m'])/10
                transition=raw-logsumexp(raw,axis=1,keepdims=True)
                total+=transition[path[i-1],path[i]]+steps[i]['emission'][path[i]]
            scores.append((float(total),path))
        expected=max(scores)[1]
        self.assertEqual([r['predicted_arc'] for r in decode(steps,10)], [steps[i]['ids'][state] for i,state in enumerate(expected)])
