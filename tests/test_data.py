import tempfile
import unittest
import zipfile
from pathlib import Path
from pathsnap.data.loading import load_trips, read_trip
from pathsnap.data.validation import validate_trip


class DataTests(unittest.TestCase):
    def test_preserves_invalid_row_ids(self):
        files = {'nodes': b'0 0\nbad\n1 1\n', 'arcs': b'0 2\n',
                 'track': b'0 0 1\n1 1 3\n', 'route': b'0\n'}
        trip = read_trip('train', 'test', files.get)
        self.assertIsNone(trip.rows['nodes'][1])
        result = validate_trip(trip)
        self.assertNotIn('arcs with invalid node references', result['issues'])
        self.assertEqual(result['issues']['gaps over one second'], 1)

    def test_invalid_values_and_references(self):
        files = {'nodes': b'0 0\n1 1\n', 'arcs': b'0 1\n2 0\n',
                 'track': b'0 0 1\n0 0 1\nnan 0 2\n', 'route': b'1\n'}
        result = validate_trip(read_trip('train', 'test', files.get))
        for issue in ['arcs with invalid node references', 'route with invalid arc references',
                      'nonincreasing timestamps', 'invalid track coordinates or nonfinite values']:
            self.assertEqual(result['issues'][issue], 1)

    def test_missing_files(self):
        trip = read_trip('train', 'test', lambda k: None)
        self.assertEqual(len(trip.issues), 4)

    def test_zip_and_directory_match_and_exclude_evaluator(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            files = {'track': b'0 0 1\n', 'nodes': b'0 0\n', 'arcs': b'0 0\n', 'route': b'0\n'}
            archive = root/'data.zip'
            with zipfile.ZipFile(archive, 'w') as z:
                for partition in ['train', 'evaluator_test']:
                    for kind, raw in files.items():
                        name = f'Student folder/{partition}/00000001/00000001.{kind}'
                        path = root/name
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_bytes(raw)
                        z.writestr(name, raw)
            zipped, directory = list(load_trips(archive)), list(load_trips(root))
            self.assertEqual(zipped, directory)
            self.assertEqual(len(zipped), 1)


if __name__ == '__main__':
    unittest.main()
