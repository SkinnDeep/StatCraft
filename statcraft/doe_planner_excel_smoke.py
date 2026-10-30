"""Actual-window and frozen DOE planner, Excel conversion and MPX acceptance."""
import copy
import math
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree as ET
from zipfile import ZipFile
from .app import Presenter,format_entry
from .model import Worksheet,Column
from .doe_planner_dialog import DOEPlannerDialog,FAMILIES
from .xlsx_export import S


def verify_doe_planner_excel(app,p,w,temp,checkpoint):
    checkpoint('Unified DOE planner: eleven families, live preview, typed XLSX, conversion and MPX')
    p.new();p.worksheet=Worksheet('Original data',[Column('Keep',values=[42,43])])
    w.refresh();app.processEvents()
    before=copy.deepcopy(p.worksheet)
    d=DOEPlannerDialog(w)
    for kind,_,_ in FAMILIES:
        d.family.setCurrentIndex(d.family.findData(kind))
        assert d.refresh_preview(),(kind,d.error.text())
        assert d.preview_sheet.row_count>0 and not d.preview_table.viewport().grab().isNull()
        assert p.worksheet==before
    d.family.setCurrentIndex(d.family.findData('general_factorial'))
    d.factor_table.cellWidget(1,1).setCurrentIndex(1);d.factor_table.item(1,2).setText('Steel, Aluminum, Brass')
    assert d.refresh_preview(),d.error.text()
    assert d.preview_sheet.columns[5].kind=='text' and d.preview_sheet.row_count==12
    excel=Path(temp)/'doe-plan.xlsx'
    with patch('statcraft.doe_planner_dialog.QFileDialog.getSaveFileName',return_value=(str(excel),'Excel')):d.export_excel()
    with ZipFile(excel) as z:
        root=ET.fromstring(z.read('xl/worksheets/sheet1.xml'))
        assert root.find('.//{'+S+'}c[@r="F2"]/{'+S+'}is/{'+S+'}t').text in ('Steel','Aluminum','Brass')
        assert not root.findall('.//{'+S+'}f')
    d.create();assert d.result()==1
    entry=p.create_doe_plan(**d.parameters)
    assert p.native_project.worksheets[0]==before and p.worksheet.row_count==12
    assert 'General Factorial' in format_entry(entry)
    w.refresh();w.show_result(entry);app.processEvents();assert w.selected_entry is entry
    # Generate another plan with the same title; the project keeps distinct tabs.
    second=p.create_doe_plan(**d.parameters);assert p.worksheet.name.endswith('(2)')
    r=DOEPlannerDialog(w);r.family.setCurrentIndex(r.family.findData('central_composite'));r.centers.setValue(2);r.replicates.setValue(2)
    assert r.refresh_preview(),r.error.text()
    created=p.create_doe_plan(**r.parameters);assert created['result']['center_runs']==4
    for index in range(4,7):assert p.worksheet.columns[index].kind=='number'
    values=[]
    for i in range(p.worksheet.row_count):
        a,b,c=[p.worksheet.columns[j].values[i] for j in (4,5,6)]
        values.append(20+2*a-3*b+.7*c+.8*a*a+.4*a*b+.03*math.sin(i))
    p.worksheet.columns.append(Column('Response',values=values))
    fit=p.analyze_response_surface(7,[4,5,6]);assert fit['result']['analysis']=='response_surface'
    target=Path(temp)/'planner.mpx';p.save(target)
    current=p.worksheet;state=(p.project_path,p.dirty,copy.deepcopy(p.history))
    all_excel=Path(temp)/'project.xlsx'
    with patch('statcraft.modern_app.QFileDialog.getSaveFileName',return_value=(str(all_excel),'Excel')):w.export_excel(True)
    assert (p.project_path,p.dirty,p.history)==state and p.worksheet is current
    with ZipFile(all_excel) as z:
        workbook=ET.fromstring(z.read('xl/workbook.xml'));assert len(workbook.find('{'+S+'}sheets'))==len(p.native_project.worksheets)
    converted=Path(temp)/'converted.xlsx';raw=target.read_bytes()
    with patch('statcraft.modern_app.QFileDialog.getOpenFileName',return_value=(str(target),'StatCraft')),patch('statcraft.modern_app.QFileDialog.getSaveFileName',return_value=(str(converted),'Excel')):w.convert_mpx_excel()
    assert target.read_bytes()==raw and converted.exists() and p.worksheet is current
    q=Presenter();q.load(target)
    assert len(q.native_project.worksheets)==len(p.native_project.worksheets)
    for sheet in q.native_project.worksheets[1:]:assert 'planner_configuration' in sheet.metadata['doe']
    saved=next(e for e in q.history if e.get('recipe',{}).get('action')=='analyze_response_surface')
    assert q.rerun_result(saved)['result']['r_squared']==saved['result']['r_squared']
    for member in ('xl/workbook.xml','[Content_Types].xml'):
        with ZipFile(converted) as z:ET.fromstring(z.read(member))
    with patch('statcraft.modern_app.QFileDialog.getOpenFileName',return_value=('','')):w.convert_mpx_excel()
    d.deleteLater();r.deleteLater()
