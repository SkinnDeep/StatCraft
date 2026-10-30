"""Original atomic XLSX worksheet-data export; no Excel installation is required."""
from pathlib import Path
import math
import os
import re
import tempfile
from xml.etree import ElementTree as ET
from zipfile import ZipFile,ZIP_DEFLATED
from .model import Worksheet,display_date

S='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
R='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
P='http://schemas.openxmlformats.org/package/2006/relationships'
C='http://schemas.openxmlformats.org/package/2006/content-types'
ET.register_namespace('',S);ET.register_namespace('r',R)


def _xml(root):return ET.tostring(root,encoding='utf-8',xml_declaration=True)
def _tag(name):return '{'+S+'}'+name


def _text(value):
    # Excel uses ST_Xstring escapes for XML-forbidden control characters.
    value=re.sub(r'_x[0-9a-fA-F]{4}_',lambda m:'_x005F_'+m.group()[1:],str(value))
    return ''.join(f'_x{ord(ch):04X}_' if ord(ch)<32 and ch not in '\t\n\r' or 0xD800<=ord(ch)<=0xDFFF or ord(ch) in (0xFFFE,0xFFFF) else ch for ch in value)


def _cell_string(row,reference,value,style=None):
    if len(value.encode('utf-16-le',errors='surrogatepass'))//2>32767:raise ValueError('Excel cells support at most 32767 UTF-16 characters.')
    attrs={'r':reference,'t':'inlineStr'}
    if style is not None:attrs['s']=str(style)
    cell=ET.SubElement(row,_tag('c'),attrs);inline=ET.SubElement(cell,_tag('is'))
    ET.SubElement(inline,_tag('t'),{'{http://www.w3.org/XML/1998/namespace}space':'preserve'}).text=_text(value)


def _column(index):
    value=''
    while index:index,remainder=divmod(index-1,26);value=chr(65+remainder)+value
    return value


def _names(sheets):
    names=[];used=set()
    for sheet in sheets:
        base=re.sub(r'[\\/*?:\[\]\x00-\x1f]','_',sheet.name).strip("'") or 'Worksheet'
        base=base.encode('utf-16-le',errors='surrogatepass')[:62].decode('utf-16-le',errors='ignore');name=base;number=2
        while name.casefold() in used:
            suffix=' ('+str(number)+')';name=base.encode('utf-16-le')[:2*(31-len(suffix))].decode('utf-16-le',errors='ignore')+suffix;number+=1
        used.add(name.casefold());names.append(name)
    return names


def _worksheet(sheet):
    root=ET.Element(_tag('worksheet'));end=_column(max(1,len(sheet.columns)))+str(sheet.row_count+1)
    ET.SubElement(root,_tag('dimension'),ref='A1:'+end)
    views=ET.SubElement(root,_tag('sheetViews'));view=ET.SubElement(views,_tag('sheetView'),workbookViewId='0')
    ET.SubElement(view,_tag('pane'),ySplit='1',topLeftCell='A2',activePane='bottomLeft',state='frozen')
    columns=ET.SubElement(root,_tag('cols'))
    for index,column in enumerate(sheet.columns,1):
        width=min(48,max(12,len(column.name)+3,22 if column.kind=='date' else 12))
        ET.SubElement(columns,_tag('col'),min=str(index),max=str(index),width=str(width),customWidth='1')
    data=ET.SubElement(root,_tag('sheetData'));header=ET.SubElement(data,_tag('row'),r='1')
    for index,column in enumerate(sheet.columns,1):_cell_string(header,_column(index)+'1',column.name,1)
    for at in range(sheet.row_count):
        row=ET.SubElement(data,_tag('row'),r=str(at+2))
        for index,column in enumerate(sheet.columns,1):
            value=column.values[at] if at<len(column.values) else None
            if value is None:continue
            reference=_column(index)+str(at+2)
            if column.kind=='text':_cell_string(row,reference,value);continue
            number=float(value);style=0
            if column.kind=='date':
                # OLE dates and Excel's 1900 date system differ before March 1900.
                if not 2<=number<2958466:_cell_string(row,reference,display_date(value));continue
                number=number-1 if number<61 else number
                style=2 if number.is_integer() else 3
            cell=ET.SubElement(row,_tag('c'),r=reference,s=str(style))
            ET.SubElement(cell,_tag('v')).text=repr(number)
    if sheet.columns:ET.SubElement(root,_tag('autoFilter'),ref='A1:'+end)
    return _xml(root)


def _styles():
    root=ET.Element(_tag('styleSheet'));formats=ET.SubElement(root,_tag('numFmts'),count='2')
    ET.SubElement(formats,_tag('numFmt'),numFmtId='164',formatCode='yyyy-mm-dd')
    ET.SubElement(formats,_tag('numFmt'),numFmtId='165',formatCode='yyyy-mm-dd hh:mm:ss.000')
    fonts=ET.SubElement(root,_tag('fonts'),count='2')
    for bold in (False,True):
        font=ET.SubElement(fonts,_tag('font'));ET.SubElement(font,_tag('sz'),val='11');ET.SubElement(font,_tag('name'),val='Calibri')
        if bold:ET.SubElement(font,_tag('b'))
    fills=ET.SubElement(root,_tag('fills'),count='3')
    for pattern in ('none','gray125','solid'):
        fill=ET.SubElement(fills,_tag('fill'));p=ET.SubElement(fill,_tag('patternFill'),patternType=pattern)
        if pattern=='solid':ET.SubElement(p,_tag('fgColor'),rgb='FFE8EEF4');ET.SubElement(p,_tag('bgColor'),indexed='64')
    borders=ET.SubElement(root,_tag('borders'),count='1');ET.SubElement(borders,_tag('border'))
    base=ET.SubElement(root,_tag('cellStyleXfs'),count='1');ET.SubElement(base,_tag('xf'),numFmtId='0',fontId='0',fillId='0',borderId='0')
    xfs=ET.SubElement(root,_tag('cellXfs'),count='4')
    for number,font,fill in ((0,0,0),(0,1,2),(164,0,0),(165,0,0)):
        ET.SubElement(xfs,_tag('xf'),numFmtId=str(number),fontId=str(font),fillId=str(fill),borderId='0',xfId='0',applyNumberFormat='1')
    styles=ET.SubElement(root,_tag('cellStyles'),count='1');ET.SubElement(styles,_tag('cellStyle'),name='Normal',xfId='0',builtinId='0')
    return _xml(root)


def write_workbook(path,sheets,protected_paths=()):
    path=Path(path)
    if path.suffix.lower()!='.xlsx':raise ValueError('Excel workbooks use the .xlsx extension.')
    for source in protected_paths:
        source=Path(source)
        if path.resolve()==source.resolve() or path.exists() and source.exists() and os.path.samefile(path,source):
            raise ValueError('Choose an Excel destination different from the source project.')
    sheets=list(sheets)
    if not sheets or len(sheets)>256:raise ValueError('Export 1 to 256 worksheets per workbook.')
    total=0
    for sheet in sheets:
        if not isinstance(sheet,Worksheet):raise ValueError('Export typed worksheets.')
        sheet.validate();total+=(sheet.row_count+1)*len(sheet.columns)
        if len(sheet.columns)>16384 or sheet.row_count>=1048576:raise ValueError('A worksheet exceeds Excel row or column limits.')
    if total>1_100_000:raise ValueError('This workbook exceeds the supported Excel export cell budget.')
    names=_names(sheets);root=ET.Element(_tag('workbook'));listed=ET.SubElement(root,_tag('sheets'))
    rels=ET.Element('Relationships',xmlns=P);types=ET.Element('Types',xmlns=C)
    ET.SubElement(types,'Default',Extension='rels',ContentType='application/vnd.openxmlformats-package.relationships+xml')
    ET.SubElement(types,'Default',Extension='xml',ContentType='application/xml')
    for part,kind in [('/xl/workbook.xml','sheet.main'),('/xl/styles.xml','styles')]:
        ET.SubElement(types,'Override',PartName=part,ContentType='application/vnd.openxmlformats-officedocument.spreadsheetml.'+kind+'+xml')
    parts={'xl/styles.xml':_styles()}
    for index,(sheet,name) in enumerate(zip(sheets,names),1):
        ET.SubElement(listed,_tag('sheet'),name=_text(name),sheetId=str(index),attrib={'{'+R+'}id':'rId'+str(index)})
        ET.SubElement(rels,'Relationship',Id='rId'+str(index),Type=R+'/worksheet',Target='worksheets/sheet'+str(index)+'.xml')
        ET.SubElement(types,'Override',PartName='/xl/worksheets/sheet'+str(index)+'.xml',ContentType='application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml')
        parts['xl/worksheets/sheet'+str(index)+'.xml']=_worksheet(sheet)
    ET.SubElement(rels,'Relationship',Id='styles',Type=R+'/styles',Target='styles.xml')
    package_rels=ET.Element('Relationships',xmlns=P);ET.SubElement(package_rels,'Relationship',Id='workbook',Type=R+'/officeDocument',Target='xl/workbook.xml')
    parts.update({'xl/workbook.xml':_xml(root),'xl/_rels/workbook.xml.rels':_xml(rels),'_rels/.rels':_xml(package_rels),'[Content_Types].xml':_xml(types)})
    handle,tmp=tempfile.mkstemp(prefix='.statcraft-xlsx-',suffix='.tmp',dir=path.parent);os.close(handle)
    try:
        with ZipFile(tmp,'w',ZIP_DEFLATED) as archive:
            for member,data in parts.items():archive.writestr(member,data)
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
    return {'worksheets':len(sheets),'sheet_names':names,'rows':[sheet.row_count for sheet in sheets],'path':str(path)}


def convert_mpx(source,destination):
    source=Path(source)
    if source.suffix.lower() not in ('.mpx','.mwx'):raise ValueError('Choose an MPX project or supported MWX worksheet.')
    from .app import Presenter
    p=Presenter();p.load(source)
    sheets=p.native_project.worksheets if p.native_project else [p.worksheet]
    return write_workbook(destination,sheets,protected_paths=[source])
