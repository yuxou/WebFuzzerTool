from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from datetime import datetime
import logging
import os
from html import escape # HTML 이스케이프를 위한 모듈 추가

def register_fonts(font_dir='fonts/'):
    """NanumGothic 폰트를 등록하여 PDF에 사용 가능하도록 설정"""
    try:
        nanum_gothic_path = os.path.join(font_dir, 'NanumGothic.ttf')
        nanum_gothic_bold_path = os.path.join(font_dir, 'NanumGothicBold.ttf')
        
        if os.path.exists(nanum_gothic_path):
            pdfmetrics.registerFont(TTFont('NanumGothic', nanum_gothic_path))
            logging.info("NanumGothic font registered successfully.")
        else:
            logging.warning(f"NanumGothic.ttf not found in {font_dir}.")
        
        # 폰트 등록
        if os.path.exists(nanum_gothic_bold_path):
            pdfmetrics.registerFont(TTFont('NanumGothic-Bold', nanum_gothic_bold_path))
            logging.info("NanumGothic 폰트 등록 성공")
        else:
            logging.warning(f"NanumGothic.ttf 파일을 {font_dir} 디렉토리에서 찾을 수 없습니다.")
        
    except Exception as e:
        logging.error(f"폰트 등록 실패: {e}")

def safe_escape(text):
    """HTML 인코딩을 수행하기 전 None 값을 빈 문자열로 처리"""
    return escape(text) if text else ''

def generate_pdf_report(crawled_urls, extraction_results, vulnerabilities, attempts, output_path='fuzzer_report.pdf'):
    """웹 퍼저 결과를 PDF로 생성"""
    register_fonts()

    # 문서 및 기본 스타일 설정
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=30,
        leftMargin=30,
        topMargin=40,
        bottomMargin=30
    )
    
    styles = getSampleStyleSheet()
    styles['Normal'].fontName = 'NanumGothic' if 'NanumGothic' in pdfmetrics.getRegisteredFontNames() else 'Helvetica'
    styles['Normal'].fontSize = 12
    styles.add(ParagraphStyle(name='Bold', fontName=styles['Normal'].fontName, fontSize=12, leading=14, textColor=colors.black, spaceAfter=6))
    
    cover_title_style = ParagraphStyle(name='CoverTitle', fontName='NanumGothic-Bold', fontSize=55, alignment=1, spaceAfter=60)
    cover_date_style = ParagraphStyle(name='CoverDate', fontName='NanumGothic', fontSize=25, alignment=1, spaceAfter=40)
    toc_style = ParagraphStyle(name='TOC', fontName='NanumGothic-Bold', fontSize=40, alignment=0, spaceAfter=50, leading=24)
    item_style = ParagraphStyle(name='item', fontName='NanumGothic', fontSize=30, alignment=0, spaceAfter=40, leading=20)

    flowables = []

    # 표지 페이지
    flowables.append(Spacer(1, 200))
    flowables.append(Paragraph("웹 퍼저 리포트", cover_title_style))
    flowables.append(Paragraph(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), cover_date_style))
    flowables.append(Spacer(1, 80))
    
    flowables.append(PageBreak())

    # 목차
    flowables.append(Paragraph("목차", toc_style))
    toc = [
        '1. 크롤링 결과',
        '2. 폼과 입력 필드',
        '3. 퍼징 시도 및 결과'
    ]
    for item in toc:
        flowables.append(Paragraph(item, item_style))
    flowables.append(PageBreak())

    # 1. 크롤링 결과
    section_title_style = ParagraphStyle(
        name='SectionTitle',
        fontName='NanumGothic-Bold',  
        fontSize=30,  
        spaceAfter=33,  
        textColor=colors.black,  
        leading=20  
    )
    flowables.append(Paragraph("1. 크롤링 결과", section_title_style))
    if crawled_urls:
        table_data = [['크롤링한 URL']]
        for url in crawled_urls:
            table_data.append([Paragraph(f"- {safe_escape(url)}", styles['Normal'])])
        
        # 테이블 스타일 설정
        table_style = TableStyle([
            ('FONTNAME', (0, 0), (0, 0), styles['Bold'].fontName),
            ('BACKGROUND', (0, 0), (0, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (0, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 1), (-1, -1), styles['Normal'].fontName),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ])
        
        # 테이블 생성
        table = Table(table_data, colWidths=[500]) 
        table.setStyle(table_style)

        # 테이블 추가
        flowables.append(table)
    else:
        flowables.append(Paragraph("크롤링한 URL이 없습니다.", styles['Normal']))

    flowables.append(PageBreak())

    # 2. 폼과 입력 필드
    flowables.append(Paragraph("2. 폼과 입력 필드", section_title_style))
    if extraction_results:
        table_data = [['URL', '폼 액션', '메소드', '입력 필드']]
        for result in extraction_results:
            for idx, form in enumerate(result.get('forms', []), start=1):
                inputs_list = ', '.join([
                    f"{safe_escape(input_field.get('name', ''))} (type: {safe_escape(input_field.get('type', ''))})" 
                    for input_field in form.get('inputs', [])
                ])
                table_data.append([
                    Paragraph(safe_escape(result['url']), styles['Normal']),
                    Paragraph(safe_escape(form.get('action', '')), styles['Normal']),
                    Paragraph(safe_escape(form.get('method', '').upper()), styles['Normal']),
                    Paragraph(inputs_list, styles['Normal'])
                ])  
        
        # 테이블 스타일 설정
        table_style = TableStyle([
            ('FONTNAME', (0, 0), (-1, 0), styles['Bold'].fontName),
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 1), (-1, -1), styles['Normal'].fontName),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ])
        
        # 테이블 생성
        table = Table(table_data, colWidths=[150, 150, 50, 150])
        table.setStyle(table_style)
        
        # 테이블 추가
        flowables.append(table)
    else:
        flowables.append(Paragraph("폼 정보가 없습니다.", styles['Normal']))
    flowables.append(PageBreak())


    # 3. 퍼징 시도 및 결과
    flowables.append(Paragraph("3. 퍼징 시도 및 결과", section_title_style))

    # 시도 데이터를 자동으로 분류할 딕셔너리 생성
    vulnerability_types = {}

    for attempt in attempts:
        # 시도의 결과에서 취약점 유형 추출
        vulnerability_type = attempt.get('result', '취약점 없음').replace(' 취약점 발견', '')
        
        # 새로운 취약점 유형이면 딕셔너리에 추가
        if vulnerability_type not in vulnerability_types:
            vulnerability_types[vulnerability_type] = []
        
        vulnerability_types[vulnerability_type].append(attempt)

    table_title_style = ParagraphStyle(name='tableTitle', fontName='NanumGothic-Bold', fontSize=23, alignment=1, spaceAfter=23)

    # 취약점 없는 시도와 기타 취약점을 구분하여 처리
    non_vulnerable_attempts = vulnerability_types.pop('취약점 없음', [])

    flowables.append(Paragraph(f"-- 취약점 발견 시도 --", table_title_style))

    # 취약점 있는 유형별로 테이블 생성
    for vuln_type, attempts in vulnerability_types.items():
        flowables.append(Paragraph(f"{vuln_type}", table_title_style))
        
        # 테이블 데이터 초기화
        table_data = [['폼 액션', '페이로드', '결과']]
        
        # 시도 데이터 추가
        for attempt in attempts:
            table_data.append([
                Paragraph(safe_escape(attempt.get('form_action', '')), styles['Normal']),
                Paragraph(safe_escape(attempt.get('payload', '')), styles['Normal']),
                Paragraph(safe_escape(attempt.get('result', '')), styles['Normal'])
            ])

        # 테이블 스타일 설정
        table_style = TableStyle([
            ('FONTNAME', (0, 0), (-1, 0), styles['Bold'].fontName),
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 1), (-1, -1), styles['Normal'].fontName),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ])
        
        # 테이블 생성
        table = Table(table_data, colWidths=[150, 150, 150])
        table.setStyle(table_style)
        
        # 테이블 추가
        flowables.append(table)
        flowables.append(PageBreak())  # 페이지 구분

    # 취약점 없는 시도 테이블을 마지막에 생성
    if non_vulnerable_attempts:
        flowables.append(Paragraph("취약점 없는 시도", table_title_style))
        table_data = [['폼 액션', '페이로드', '결과']]
        for attempt in non_vulnerable_attempts:
            table_data.append([
                Paragraph(safe_escape(attempt.get('form_action', '')), styles['Normal']),
                Paragraph(safe_escape(attempt.get('payload', '')), styles['Normal']),
                Paragraph(safe_escape(attempt.get('result', '')), styles['Normal'])
            ])

        # 테이블 스타일 설정
        table_style = TableStyle([
            ('FONTNAME', (0, 0), (-1, 0), styles['Bold'].fontName),
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 1), (-1, -1), styles['Normal'].fontName),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ])
        
        # 테이블 생성
        table = Table(table_data, colWidths=[150, 150, 150])
        table.setStyle(table_style)

        # 테이블 추가
        flowables.append(table)
    else:
        flowables.append(Paragraph("취약점 없는 시도가 없습니다.", table_title_style))

    # PDF 생성
    try:
        doc.build(flowables)
        logging.info(f"[PDFReport] 리포트가 {output_path}에 생성되었습니다.")
    except Exception as e:
        logging.error(f"[PDFReport] PDF 생성 중 오류 발생: {e}")