"""Check bundled application bytecode against current rebuild sources."""
import sys,types,marshal,json
from pathlib import Path
from PyInstaller.archive.readers import CArchiveReader

def normalized(code):
    return code.replace(co_filename='',co_consts=tuple(normalized(v) if isinstance(v,types.CodeType) else v for v in code.co_consts))

def verify(executable):
    root=Path(__file__).resolve().parent
    archive=CArchiveReader(str(executable));pyz=archive.open_embedded_archive(next(name for name,value in archive.toc.items() if value[-1]=='z'))
    checked=[];mismatches=[]
    for source in sorted((root/'statcraft').glob('*.py')):
        name='statcraft' if source.stem=='__init__' else 'statcraft.'+source.stem
        if name not in pyz.toc:continue
        current=compile(source.read_bytes(),str(source),'exec',dont_inherit=True,optimize=0)
        if normalized(current)!=normalized(pyz.extract(name)):mismatches.append(name)
        checked.append(name)
    required={'statcraft.response_surface_catalog','statcraft.response_surface_blocked','statcraft.response_surface_catalog_smoke','statcraft.graph_hover','statcraft.chart_hover_smoke','statcraft.native_mpx_outputs','statcraft.native_output_chart','statcraft.native_output_smoke','statcraft.response_surface_dialogs','statcraft.mixture_condition','statcraft.mixture_condition_dialogs','statcraft.mixture_condition_smoke','statcraft.plot_ticks','statcraft.mixture_process_model','statcraft.mixture_process_report','statcraft.mixture_process_dialogs','statcraft.mixture_process_smoke','statcraft.mixture_multi_optimizer','statcraft.mixture_multi_optimizer_dialog','statcraft.mixture_multi_chart','statcraft.mixture_multi_report','statcraft.mixture_multi_smoke','statcraft.mixture_exploration','statcraft.mixture_exploration_chart','statcraft.mixture_exploration_report','statcraft.mixture_exploration_dialogs','statcraft.mixture_exploration_smoke','statcraft.dynamic_taguchi_analysis','statcraft.dynamic_taguchi_report','statcraft.dynamic_taguchi_dialog','statcraft.dynamic_taguchi_chart','statcraft.dynamic_taguchi_smoke','statcraft.mixture_analysis','statcraft.mixture_report','statcraft.taguchi_analysis','statcraft.taguchi_analysis_report','statcraft.doe_analysis_charts','statcraft.doe_analysis_dialogs','statcraft.mixture_prediction_dialog','statcraft.mixture_taguchi_smoke','statcraft.doe_planner','statcraft.doe_planner_dialog','statcraft.doe_catalog_designs','statcraft.doe_special_designs','statcraft.doe_planner_excel_smoke','statcraft.xlsx_export','statcraft.multiple_capability_engine','statcraft.multiple_capability_report','statcraft.multiple_capability_dialogs','statcraft.multiple_capability_chart','statcraft.multiple_capability_smoke','statcraft.new_analysis_integrity_smoke','statcraft.snapshot_chart','statcraft.reliability_inputs','statcraft.reliability_engine','statcraft.msa_dialogs','statcraft.msa_attribute_engine','statcraft.analysis_bindings','statcraft.attribute_capability','statcraft.attribute_capability_dialogs','statcraft.attribute_capability_chart','statcraft.attribute_capability_report','statcraft.attribute_capability_smoke','statcraft.app','statcraft.modern_app','statcraft.recipes','statcraft.recipe_columns','statcraft.prediction','statcraft.prediction_dialogs','statcraft.prediction_report','statcraft.prediction_smoke'}
    missing=sorted(required-set(checked))
    source=root/'launch_modern.py'
    if normalized(compile(source.read_bytes(),str(source),'exec',dont_inherit=True,optimize=0))!=normalized(marshal.loads(archive.extract('launch_modern'))):mismatches.append('launch_modern')
    proof=dict(application_modules_checked=len(checked)+1,missing_required=missing,bytecode_mismatches=mismatches,source_code_matches=not missing and not mismatches)
    if not proof['source_code_matches']:raise ValueError(json.dumps(proof))
    return proof

if __name__=='__main__':print(json.dumps(verify(Path(sys.argv[1])),indent=2))
