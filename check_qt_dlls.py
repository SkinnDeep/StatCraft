import ast, sys
from pathlib import Path
sys.path.insert(0, str(Path('work/statcraft-build-deps').resolve()))
import pefile
rows=ast.literal_eval(Path('work/statcraft-modern-freeze/modern/PKG-00.toc').read_text())[2]
libraries={Path(dest).name.lower():Path(src) for dest,src,kind in rows if kind in ('BINARY','EXTENSION')}
cache={}
failures=[]
def load(path,directories):
    # Qt6Core exports exceed pefile's default 8192-name inspection budget.
    # A truncated export list produces false unresolved-import reports.
    image=pefile.PE(str(path),fast_load=True,max_symbol_exports=100000)
    image.parse_data_directories(directories=directories)
    if any('export' in warning.lower() and 'assuming corrupt' in warning.lower() for warning in image.get_warnings()):
        raise ValueError('Export inspection was truncated: '+str(path))
    return image
for name,path in libraries.items():
    binding=path.suffix.lower()=='.pyd' and any(part.lower() in ('pyside6','shiboken6') for part in path.parts)
    if not (name.startswith('qt6') or name.startswith('pyside') or name.startswith('shiboken') or binding): continue
    pe=load(path,[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_IMPORT']])
    for dep in getattr(pe,'DIRECTORY_ENTRY_IMPORT',[]):
        depname=dep.dll.decode().lower()
        if depname not in libraries:
            if depname.startswith(('qt6','pyside','shiboken')):failures.append((name,depname,['Required bundled Qt library is missing']))
            continue
        if depname not in cache:
            target=load(libraries[depname],[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_EXPORT']]); exports=getattr(target,'DIRECTORY_ENTRY_EXPORT',None)
            cache[depname]={s.name for s in exports.symbols} if exports else set()
        missing=[i.name.decode(errors='replace') for i in dep.imports if i.name and i.name not in cache[depname]]
        if missing:failures.append((name,depname,missing))
if failures:
    for name,dependency,missing in failures:print(name,dependency,missing)
    raise SystemExit(1)
msg = 'Bundled Qt/PySide/Shiboken import/export dependencies verified without export truncation.'
for out_name in ('work/preview89-qt-dlls-verified.log', 'work/preview90-qt-dlls-verified.log', 'work/preview91-qt-dlls-verified.log', 'work/preview92-qt-dlls-verified.log', 'work/preview93-qt-dlls-verified.log', 'work/preview94-qt-dlls-verified.log', 'work/preview95-qt-dlls-verified.log', 'work/preview96-qt-dlls-verified.log', 'work/preview97-qt-dlls-verified.log', 'work/preview98-qt-dlls-verified.log'):
    Path(out_name).write_text(msg, encoding='utf-8')
print(msg)
