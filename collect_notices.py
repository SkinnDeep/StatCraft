"""Retain notices for the bundled numerical runtime and ancillary modules."""
from pathlib import Path
import hashlib

root = Path(__file__).resolve().parent
deps = root.parent / 'statcraft-build-deps'
runtime = Path('C:/Users/funny/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/Lib/site-packages')
selected = [deps / 'setuptools', deps / 'setuptools-84.0.0.dist-info',
            deps / 'numpy-2.5.4.dist-info', deps / 'scipy-1.18.1.dist-info', deps / 'scipy']
for name in ('cffi-2.1.1.dist-info', 'pycparser-3.0.dist-info',
             'charset_normalizer-3.5.2.dist-info', 'typing_extensions-4.16.0.dist-info'):
    selected.append(runtime / name)
parts = []
seen = set()
for directory in selected:
    for path in sorted(directory.rglob('*')):
        if path.is_file() and path.name.lower().startswith(('license', 'copying')):
            data = path.read_bytes()
            digest = hashlib.sha256(data).hexdigest()
            if digest not in seen:
                seen.add(digest)
                parts.append(str(path.relative_to(directory.parent)) + '\n\n' + data.decode('utf-8', errors='replace'))
(root / 'notices/Additional-runtime-notices.txt').write_text('\n\n'.join(parts), encoding='utf-8')
print(f'Retained {len(parts)} additional unique notices.')
