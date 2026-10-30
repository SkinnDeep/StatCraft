"""Original OOXML exporters. No Office installation, COM or vendor runtime."""
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape
import os
import re
import struct
import tempfile
import textwrap

R='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
REL='http://schemas.openxmlformats.org/package/2006/relationships'
CT='http://schemas.openxmlformats.org/package/2006/content-types'
W='http://schemas.openxmlformats.org/wordprocessingml/2006/main'
P='http://schemas.openxmlformats.org/presentationml/2006/main'
A='http://schemas.openxmlformats.org/drawingml/2006/main'
XML='<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'


def clean(value):
    return ''.join(c for c in str(value) if c in '\t\n\r' or 32<=ord(c)<=0xD7FF or 0xE000<=ord(c)<=0xFFFD or 0x10000<=ord(c)<=0x10FFFF)


@dataclass(frozen=True)
class OfficeSnapshot:
    title: str
    report: str
    png: bytes = b''

    def validate(self):
        if len(self.report)>2000000 or len(self.title)>1000: raise ValueError('Output is too large for an Office export.')
        if not self.report and not self.png: raise ValueError('There is no report or graph to export.')
        if self.png: png_size(self.png)


def report_text(entry):
    """Describe expanded graph output without dumping renderer data arrays."""
    result=entry.get('result',{})
    if result.get('graph')!='expanded':
        from .app import format_entry
        return format_entry(entry)
    lines=[entry.get('title','Graph'),entry.get('time',''),'']
    for panel in result.get('panels',[]):
        lines.append(str(panel.get('title',result.get('label','Graph'))))
        names=panel.get('x_labels',panel.get('axes',[]))
        if names:lines.append('Variables: '+', '.join(str(x) for x in names))
        if panel.get('kind')=='heatmap':
            values=panel.get('values',[])
            lines.extend(['Rows: '+str(len(values)),'Columns: '+str(len(values[0]) if values else 0)])
        else:
            for key in ('points','rows','categories'):
                if key in panel:lines.append(('Categories' if key=='categories' else 'Observations')+': '+str(len(panel[key])));break
        if panel.get('kind')=='stem_leaf':lines.extend(panel.get('lines',[]))
        lines.append('')
    return '\n'.join(lines)


def png_size(data):
    if len(data)<24 or data[:8]!=b'\x89PNG\r\n\x1a\n' or data[12:16]!=b'IHDR':raise ValueError('Graph capture is not a PNG image.')
    width,height=struct.unpack('>II',data[16:24])
    if not 0<width<=50000 or not 0<height<=50000:raise ValueError('Graph capture dimensions are unsupported.')
    return width,height


def rels(items):
    root=ET.Element('Relationships',xmlns=REL)
    for key,kind,target in items:ET.SubElement(root,'Relationship',Id=key,Type=R+'/'+kind,Target=target)
    return ET.tostring(root,encoding='utf-8',xml_declaration=True)


def atomic_package(path, parts):
    path=Path(path)
    handle,tmp=tempfile.mkstemp(prefix='.statcraft-export-',suffix='.tmp',dir=path.parent)
    os.close(handle)
    try:
        with ZipFile(tmp,'w',ZIP_DEFLATED) as z:
            for name,data in parts.items():z.writestr(name,data)
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)


def fit_image(png, max_width, max_height):
    width,height=png_size(png);scale=min(max_width/width,max_height/height)
    return max(1,int(width*scale)),max(1,int(height*scale))


def export_docx(path, snapshot):
    snapshot.validate()
    # Preserve fixed-width numerical columns instead of wrapping their headings
    # independently from the values. Ordinary reports retain portrait pages.
    longest=max((len(line.expandtabs(4)) for line in snapshot.report.splitlines()),default=0)
    landscape=longest>110
    page_width,page_height=(15840,12240) if landscape else (12240,15840)
    text_width_points=(page_width-2160)/20
    report_half_points=max(15,min(17,int(2*text_width_points/max(1,longest)/0.6)))
    def paragraph(text,style='Normal'):
        return '<w:p><w:pPr><w:pStyle w:val="'+style+'"/></w:pPr><w:r><w:t xml:space="preserve">'+escape(clean(text))+'</w:t></w:r></w:p>'
    body=paragraph(snapshot.title,'Title')
    relationships=[('styles','styles','styles.xml')]
    if snapshot.png:
        width,height=fit_image(snapshot.png,int(text_width_points*12700),(page_height-3600)*635)
        body+=f'''<w:p><w:r><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="{width}" cy="{height}"/><wp:docPr id="1" name="Graph" descr="{escape(clean(snapshot.title),{chr(34):'&quot;'})}"/><wp:cNvGraphicFramePr><a:graphicFrameLocks noChangeAspect="1"/></wp:cNvGraphicFramePr><a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:pic><pic:nvPicPr><pic:cNvPr id="1" name="Graph"/><pic:cNvPicPr/></pic:nvPicPr><pic:blipFill><a:blip r:embed="graph"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill><pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{width}" cy="{height}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>'''
        relationships.append(('graph','image','media/graph.png'))
        if snapshot.report:body+='<w:p><w:r><w:br w:type="page"/></w:r></w:p>'
    for line in clean(snapshot.report).expandtabs(4).splitlines():body+=paragraph(line,'ReportText')
    orientation=' w:orient="landscape"' if landscape else ''
    body+=f'<w:sectPr><w:pgSz w:w="{page_width}" w:h="{page_height}"{orientation}/><w:pgMar w:top="1080" w:right="1080" w:bottom="1080" w:left="1080"/></w:sectPr>'
    document=XML+f'<w:document xmlns:w="{W}" xmlns:r="{R}" xmlns:a="{A}" xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"><w:body>{body}</w:body></w:document>'
    styles=XML+f'''<w:styles xmlns:w="{W}"><w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:pPr><w:spacing w:after="80"/></w:pPr><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/><w:sz w:val="22"/><w:color w:val="000000"/></w:rPr></w:style><w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:pPr><w:keepNext/><w:spacing w:after="240"/></w:pPr><w:rPr><w:b/><w:sz w:val="36"/></w:rPr></w:style><w:style w:type="paragraph" w:styleId="ReportText"><w:name w:val="Report Text"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/></w:pPr><w:rPr><w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/><w:sz w:val="17"/></w:rPr></w:style></w:styles>'''
    styles=styles.replace('<w:sz w:val="17"/>',f'<w:sz w:val="{report_half_points}"/>')
    types=XML+f'<Types xmlns="{CT}"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Default Extension="png" ContentType="image/png"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/></Types>'
    parts={'[Content_Types].xml':types,'_rels/.rels':rels([('office','officeDocument','word/document.xml')]),'word/document.xml':document,'word/styles.xml':styles,'word/_rels/document.xml.rels':rels(relationships)}
    if snapshot.png:parts['word/media/graph.png']=snapshot.png
    atomic_package(path,parts)


def report_pages(text, width=100, lines_per_page=25):
    lines=[]
    for line in clean(text).expandtabs(4).splitlines():
        lines.extend(textwrap.wrap(line,width=width,replace_whitespace=False,drop_whitespace=False) or [''])
    pages=[lines[i:i+lines_per_page] for i in range(0,len(lines),lines_per_page)]
    if len(pages)>200:raise ValueError('Report exceeds 200 slides. Export a smaller report or use Word.')
    return pages


def _text_shape(identifier,name,lines,x,y,width,height,size,font='Calibri',bold=False):
    def para(line):
        return f'<a:p><a:pPr><a:lnSpc><a:spcPct val="110000"/></a:lnSpc></a:pPr><a:r><a:rPr lang="en-US" sz="{size}" b="{int(bold)}"><a:solidFill><a:srgbClr val="000000"/></a:solidFill><a:latin typeface="{font}"/><a:ea typeface="{font}"/><a:cs typeface="{font}"/></a:rPr><a:t xml:space="preserve">{escape(clean(line))}</a:t></a:r><a:endParaRPr sz="{size}"/></a:p>'
    return f'<p:sp><p:nvSpPr><p:cNvPr id="{identifier}" name="{name}"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr><p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{width}" cy="{height}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/><a:ln><a:noFill/></a:ln></p:spPr><p:txBody><a:bodyPr wrap="square" lIns="0" tIns="0" rIns="0" bIns="0" anchor="t"/><a:lstStyle/>{"".join(para(line) for line in lines)}</p:txBody></p:sp>'


def export_pptx(path,snapshot):
    snapshot.validate();pages=report_pages(snapshot.report)
    slides=([None] if snapshot.png else [])+pages
    with ZipFile(Path(__file__).with_name('office-template.pptx')) as z:parts={name:z.read(name) for name in z.namelist()}
    for name in list(parts):
        if name.startswith(('ppt/slides/','ppt/notesSlides/')):del parts[name]
    presentation=ET.fromstring(parts['ppt/presentation.xml']);ids=presentation.find('{'+P+'}sldIdLst');ids.clear()
    relationships=ET.fromstring(parts['ppt/_rels/presentation.xml.rels'])
    for child in list(relationships):
        if child.get('Type','').endswith('/slide'):relationships.remove(child)
    content=ET.fromstring(parts['[Content_Types].xml'])
    for child in list(content):
        if child.get('PartName','').startswith(('/ppt/slides/','/ppt/notesSlides/')):content.remove(child)
    if snapshot.png:
        ET.SubElement(content,'{'+CT+'}Default',Extension='png',ContentType='image/png');parts['ppt/media/graph.png']=snapshot.png
    for i,lines in enumerate(slides,1):
        key=f'exportSlide{i}'
        ET.SubElement(ids,'{'+P+'}sldId',{'id':str(255+i),'{'+R+'}id':key})
        ET.SubElement(relationships,'{'+REL+'}Relationship',Id=key,Type=R+'/slide',Target=f'/ppt/slides/slide{i}.xml')
        ET.SubElement(content,'{'+CT+'}Override',PartName=f'/ppt/slides/slide{i}.xml',ContentType='application/vnd.openxmlformats-officedocument.presentationml.slide+xml')
        title_size=2800 if len(snapshot.title)<100 else 1800
        shapes=_text_shape(2,'Output title',[snapshot.title],571500,381000,11049000,952500,title_size,bold=True)
        srels=[('layout','slideLayout','../slideLayouts/slideLayout6.xml')]
        if lines is None:
            width,height=fit_image(snapshot.png,11049000,4667250);x=(12192000-width)//2;y=1428750+(4667250-height)//2
            shapes+=f'<p:pic><p:nvPicPr><p:cNvPr id="3" name="Graph"/><p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr><p:nvPr/></p:nvPicPr><p:blipFill><a:blip r:embed="graph"/><a:stretch><a:fillRect/></a:stretch></p:blipFill><p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{width}" cy="{height}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr></p:pic>'
            srels.append(('graph','image','../media/graph.png'))
        else:shapes+=_text_shape(3,'Report text',lines,571500,1428750,11049000,4667250,1300,'Consolas')
        shapes+=_text_shape(4,'Page number',[f'{i} / {len(slides)}'],10858500,6381750,762000,285750,1000)
        parts[f'ppt/slides/slide{i}.xml']=XML+f'<p:sld xmlns:p="{P}" xmlns:a="{A}" xmlns:r="{R}"><p:cSld><p:bg><p:bgPr><a:solidFill><a:srgbClr val="FFFFFF"/></a:solidFill><a:effectLst/></p:bgPr></p:bg><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>{shapes}</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>'
        parts[f'ppt/slides/_rels/slide{i}.xml.rels']=rels(srels)
    ET.register_namespace('p',P);ET.register_namespace('r',R)
    ET.register_namespace('',REL)
    parts['ppt/presentation.xml']=ET.tostring(presentation,encoding='utf-8',xml_declaration=True)
    parts['ppt/_rels/presentation.xml.rels']=ET.tostring(relationships,encoding='utf-8',xml_declaration=True)
    ET.register_namespace('',CT)
    parts['[Content_Types].xml']=ET.tostring(content,encoding='utf-8',xml_declaration=True)
    atomic_package(path,parts)
    return len(slides)
