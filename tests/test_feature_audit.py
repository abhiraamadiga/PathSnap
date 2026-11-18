import gzip
import json
import tempfile
import unittest
from pathlib import Path
from pathsnap.features.audit import audit_trip
from pathsnap.features.preprocessing import FEATURES


class AuditTests(unittest.TestCase):
    def run_audit(self,observations,labels):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name,rows in [('observations',observations),('weak_labels',labels)]:
                with gzip.open(root/f'{name}.jsonl.gz','wt') as f:
                    for row in rows:f.write(json.dumps(row)+'\n')
            return audit_trip(root)

    def test_counts_and_moments(self):
        candidate={'arc_id':4,**dict.fromkeys(FEATURES,2.0)}
        observations=[{'observation_id':0,'status':'ok','candidates':[candidate]},
                      {'observation_id':1,'status':'no_candidates','candidates':[]}]
        labels=[{'observation_id':0,'arc_id':4},{'observation_id':1,'arc_id':5}]
        counts,stats=self.run_audit(observations,labels)
        self.assertEqual(counts['usable_observations'],1)
        self.assertEqual(counts['weak_label_candidate_misses'],1)
        self.assertEqual(stats['distance_m'],[1,2,0,2,2])

    def test_reject_misaligned_labels(self):
        with self.assertRaises(ValueError):
            self.run_audit([{'observation_id':0,'status':'ok','candidates':[]}],[{'observation_id':1,'arc_id':None}])

    def test_reject_labels_in_features(self):
        with self.assertRaises(ValueError):
            self.run_audit([{'observation_id':0,'status':'ok','candidates':[],'label':1}],[{'observation_id':0,'arc_id':None}])

    def test_flags_nonfinite_values(self):
        candidate={'arc_id':4,**dict.fromkeys(FEATURES,0.0)};candidate['distance_m']=float('nan')
        counts,_=self.run_audit([{'observation_id':0,'status':'ok','candidates':[candidate]}],[{'observation_id':0,'arc_id':None}])
        self.assertEqual(counts['invalid_feature_values'],1)
