"""Deterministic complaint and print pack, with user-reviewed facts only."""
from . import formal
import io
import os
from pathlib import Path
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from html import escape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image as PDFImage

FONT_CANDIDATES = [
    *[(family,Path(__file__).with_name('fonts')/(family+'-Regular.ttf')) for family in ['NotoSans','NotoSansDevanagari','NotoSansBengali','NotoSansTamil','NotoSansTelugu']],
    ('Indic',Path(os.getenv('WINDIR','C:/Windows'))/'Fonts'/'Nirmala.ttf'),
    ('Devanagari',Path('/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf')),
    ('Bengali',Path('/usr/share/fonts/truetype/noto/NotoSansBengali-Regular.ttf')),
    ('Tamil',Path('/usr/share/fonts/truetype/noto/NotoSansTamil-Regular.ttf')),
    ('Telugu',Path('/usr/share/fonts/truetype/noto/NotoSansTelugu-Regular.ttf')),
    ('Unicode',Path('/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf')),
]
AVAILABLE=[]
for name,path in FONT_CANDIDATES:
    if path.exists():
        pdfmetrics.registerFont(TTFont(name,str(path),shapable=True))
        AVAILABLE.append(name)

def unicode_markup(text):
    parts=[]; current=None; run=''
    for ch in text:
        font='Helvetica' if ord(ch)<128 else next((name for name in AVAILABLE if ord(ch) in pdfmetrics.getFont(name).face.charToGlyph),None)
        if not font:
            # Preserve exact character identity, never silently print a black square.
            ch=f'[U+{ord(ch):04X}]';font='Helvetica'
        if font!=current and run:
            parts.append(f'<font name="{current}">{escape(run)}</font>');run=''
        current=font;run+=ch
    if run: parts.append(f'<font name="{current}">{escape(run)}</font>')
    return ''.join(parts).replace('\n','<br/>')

def complaint(case):
    f=formal.fields(case)
    lines=[f"Subject: Request for assistance - {f['category'].replace('_',' ')}",f"Case: {case['id']}",
        f"To: {f.get('entity_name') or case['route']['title']}", '', 'I request assistance with the following grievance.',f['description'],'', 'Details supplied by the complainant:']
    for field in ['entity_name','amount','incident_date','payment_method','transaction_reference','recipient']:
        value=f.get(field)
        lines.append(f"{field.replace('_',' ').title()}: {'INR '+str(value) if field=='amount' and value is not None else value if value is not None else 'Not provided'}")
    lines += ['', 'Requested action:',f.get('desired_resolution') or 'Please investigate, provide a written explanation and inform me of the available redressal steps.', '', 'Evidence:']
    lines += [f"{i+1}. {e['name']} (SHA-256: {e['sha256']})" for i,e in enumerate(case['evidence'])] or ['No evidence attached.']
    lines += ['', 'I confirm that the information above reflects my account to the best of my knowledge.', 'Name: ____________________    Signature: ____________________    Date: __________', '', 'Prepared by Grievance Clock. This document is not a filing acknowledgement.']
    return '\n'.join(lines)

def pdf(case, offline=False, read_evidence=None):
    out=io.BytesIO()
    styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name='GCBody',fontName='Helvetica',fontSize=10,leading=15,textColor=colors.HexColor('#25332f'),spaceAfter=8,shaping=True))
    story=[]
    def p(t,style='GCBody'):
        # Complaint is normalized English; original-language records remain available in the ZIP.
        safe=unicode_markup(str(t))
        story.append(Paragraph(safe,styles[style]))
    p('GRIEVANCE CLOCK','Title')
    p('PHYSICAL ACTION PACK' if offline else 'COMPLAINT & EVIDENCE INDEX','Heading2')
    p(case['id']+' | Prepared for your review | Not proof of submission')
    story.append(Spacer(1,14))
    for line in (case.get('draft') or complaint(case)).split('\n'): p(line)
    if read_evidence:
        for ev in case['evidence']:
            if ev.get('mime','').startswith('image/'):
                story.append(PageBreak())
                p('Evidence preview: '+ev['name'],'Heading2')
                picture=PDFImage(io.BytesIO(read_evidence(ev['id'])))
                picture._restrictSize(500,620)
                story.append(picture)
                p('SHA-256: '+ev['sha256'])
    if offline:
        story.append(PageBreak())
        p('Your branch visit checklist','Heading1')
        for t in ['1. Contact your own DP / registrar and confirm the current form and required documents.',
          '2. Print this complaint and the relevant evidence. This pack is not an official ISR or transmission form.',
          '3. Ask the institution whether identity proof, holding statement, death certificate, nominee / succession documents or bank verification apply to your case. Requirements vary.',
          '4. Complete signatures, attestation or bank stamps only where the official form requires them.',
          '5. Submit the documents and keep a dated, stamped acknowledgement.',
          '6. Record that acknowledgement in Grievance Clock to start your follow-up reminder.']:
            p(t)
        p('Find your institution in the official NSDL directory:')
        p('https://nsdl.com/participant/securities-company-search')
        p('No branch address has been inferred. Confirm the address and opening hours directly with the institution.')
    def footer(canvas, doc):
        canvas.setFont('Helvetica',8)
        canvas.setFillColor(colors.HexColor('#65786f'))
        canvas.drawString(42,28,'Grievance Clock | Private case document')
        canvas.drawRightString(553,28,f'Page {doc.page}')
    SimpleDocTemplate(out,pagesize=(595,842),leftMargin=42,rightMargin=42,topMargin=40,bottomMargin=48).build(story,onFirstPage=footer,onLaterPages=footer)
    return out.getvalue()
