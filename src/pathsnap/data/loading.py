"""Read trip files without changing their row-based node and arc identifiers."""
from dataclasses import dataclass
from pathlib import Path
import zipfile

COLUMNS = {"track": 3, "nodes": 2, "arcs": 2, "route": 1}
PARTITIONS = {"train": 80, "student_test": 10}


@dataclass
class Trip:
    partition: str
    trip_id: str
    rows: dict
    sizes: dict
    issues: list


def read_trip(partition, trip_id, read):
    rows, sizes, issues = {}, {}, []
    for kind, width in COLUMNS.items():
        raw = read(kind)
        if raw is None:
            issues.append(f"missing {kind} file")
            rows[kind], sizes[kind] = [], 0
            continue
        sizes[kind] = len(raw)
        parsed = []
        for index, line in enumerate(raw.decode('utf-8-sig').splitlines()):
            # Preserve malformed rows as None: dropping them would renumber IDs.
            try:
                cells = line.split()
                if len(cells) != width:
                    raise ValueError('column count')
                convert = int if kind in ('arcs', 'route') else float
                parsed.append(tuple(convert(v) for v in cells))
            except ValueError:
                parsed.append(None)
                issues.append(f"{kind} row {index}: invalid columns or values")
        if not parsed:
            issues.append(f"empty {kind} file")
        rows[kind] = parsed
    return Trip(partition, trip_id, rows, sizes, issues)


def load_trips(source):
    """Yield train/student_test trips from supplied ZIP or extracted dataset root.

    The directory must contain train/ and student_test/, optionally beneath
    'Student folder/'. Evaluator data is deliberately excluded.
    """
    source = Path(source)
    if source.is_file():
        with zipfile.ZipFile(source) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)):
                raise ValueError('Duplicate ZIP member names')
            grouped = {}
            for name in names:
                parts = name.split('/')
                if len(parts) >= 3 and parts[-3] in PARTITIONS and parts[-1]:
                    key = (parts[-3], parts[-2])
                    group = grouped.setdefault(key, {})
                    kind = Path(parts[-1]).suffix.lstrip('.')
                    if kind in COLUMNS:
                        if parts[-1] != f'{parts[-2]}.{kind}' or kind in group:
                            raise ValueError(f'Ambiguous trip file: {name}')
                        group[kind] = name
            for (partition, trip_id), files in sorted(grouped.items()):
                yield read_trip(partition, trip_id, lambda k: archive.read(files[k]) if k in files else None)
    else:
        if (source / 'Student folder').is_dir():
            source = source / 'Student folder'
        for partition in PARTITIONS:
            root = source / partition
            if root.is_dir():
                for folder in sorted(root.iterdir()):
                    if folder.is_dir():
                        def read(kind):
                            file = folder / f'{folder.name}.{kind}'
                            return file.read_bytes() if file.is_file() else None
                        yield read_trip(partition, folder.name, read)
