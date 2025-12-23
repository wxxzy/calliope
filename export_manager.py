import os
import io
from fpdf import FPDF
from ebooklib import epub
import logging
import tempfile

logger = logging.getLogger(__name__)

def export_as_markdown(title: str, content: str) -> str:
    """导出为 Markdown 字符串"""
    return f"# {title}\n\n{content}"

def export_as_pdf(title: str, content: str) -> bytes:
    """导出为 PDF 字节流"""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_left_margin(15)
    pdf.set_right_margin(15)
    
    # 1. 字体加载
    font_added = False
    possible_fonts = [
        "C:/Windows/Fonts/simhei.ttf", # Windows
        "C:/Windows/Fonts/msyh.ttc",   # Windows 微软雅黑
        "/usr/share/fonts/truetype/droid/SansFallback.ttf", # Linux
        "/System/Library/Fonts/STHeiti Light.ttc" # macOS
    ]
    
    for font_path in possible_fonts:
        if os.path.exists(font_path):
            try:
                pdf.add_font("Chinese", "", font_path)
                pdf.add_font("Chinese", "B", font_path)
                pdf.set_font("Chinese", size=12)
                font_added = True
                break
            except Exception:
                continue
    
    if not font_added:
        pdf.set_font("Helvetica", size=12)

    # 2. 绘制标题
    pdf.set_font(pdf.font_family, "B", 20)
    pdf.cell(0, 20, title, ln=True, align="C")
    pdf.ln(10)
    
    # 3. 绘制正文 (按段落处理)
    pdf.set_font(pdf.font_family, size=12)
    paragraphs = content.split('\n')
    for p in paragraphs:
        p = p.strip()
        if not p:
            pdf.ln(5) # 处理空行
            continue
        try:
            # multi_cell 自动换行
            pdf.multi_cell(0, 8, p)
            pdf.ln(2) # 段落间距
        except Exception as e:
            logger.error(f"PDF渲染段落失败: {e}")
            continue
    
    # 显式转换为 bytes，解决 bytearray 类型不兼容问题
    return bytes(pdf.output())

def export_as_epub(title: str, content: str) -> bytes:
    """导出为 EPUB 字节流"""
    book = epub.EpubBook()
    book.set_identifier(f"calliope_{title.replace(' ', '_')}")
    book.set_title(title)
    book.set_language('zh')
    book.add_author('Calliope AI Writer')
    
    # 格式化正文为 HTML 段落
    lines = content.split('\n')
    formatted_body = ""
    for line in lines:
        line = line.strip()
        if line:
            formatted_body += f"<p>{line}</p>\n"
        else:
            formatted_body += "<br/>\n"

    chapter = epub.EpubHtml(title=title, file_name='main.xhtml', lang='zh')
    chapter.content = f"<html><head><meta charset='UTF-8'></head><body><h1>{title}</h1>{formatted_body}</body></html>"
    
    book.add_item(chapter)
    book.spine = ['nav', chapter]
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    
    # 使用临时文件写入
    with tempfile.NamedTemporaryFile(delete=False, suffix='.epub') as tmp:
        temp_path = tmp.name
    
    try:
        epub.write_epub(temp_path, book)
        with open(temp_path, 'rb') as f:
            data = f.read()
        return data
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)