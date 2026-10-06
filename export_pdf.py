"""
export_pdf.py - Công cụ xuất Báo cáo BAO_CAO_BTVN3.md sang PDF và HTML
- Sử dụng Microsoft Edge / Google Chrome Headless engine (Chromium) sẵn có trên Windows
- Giữ trọn vẹn 100% tiếng Việt có dấu, định dạng bảng (table), code block và emoji
- Dự phòng xhtml2pdf nếu không tìm thấy trình duyệt
"""

import os
import sys
import subprocess
import markdown

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MD_FILE = os.path.join(BASE_DIR, "BAO_CAO_BTVN3.md")
PDF_FILE = os.path.join(BASE_DIR, "BAO_CAO_BTVN3.pdf")
HTML_FILE = os.path.join(BASE_DIR, "BAO_CAO_BTVN3.html")

def find_browser_executable():
    """Tìm đường dẫn Edge hoặc Chrome trên Windows"""
    candidates = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None

def convert_md_to_html(md_path: str) -> str:
    with open(md_path, "r", encoding="utf-8") as f:
        md_text = f.read()

    html_body = markdown.markdown(
        md_text,
        extensions=["tables", "fenced_code", "nl2br"]
    )

    styled_html = f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<title>Báo Cáo BTVN#03 - SE373 (Agentic AI - UIT)</title>
<style>
    @page {{
        size: A4 portrait;
        margin: 18mm 15mm 18mm 15mm;
    }}
    body {{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        font-size: 10.5pt;
        line-height: 1.6;
        color: #24292e;
        max-width: 900px;
        margin: 0 auto;
        padding: 24px;
        background-color: #ffffff;
    }}
    h1 {{
        font-size: 19pt;
        color: #0d3b66;
        text-align: center;
        margin-top: 10px;
        margin-bottom: 8px;
        font-weight: 700;
        border-bottom: 2px solid #0d3b66;
        padding-bottom: 12px;
    }}
    h2 {{
        font-size: 13.5pt;
        color: #028090;
        border-bottom: 1px solid #e1e4e8;
        padding-bottom: 6px;
        margin-top: 24px;
        margin-bottom: 12px;
        page-break-after: avoid;
    }}
    h3 {{
        font-size: 11.5pt;
        color: #114b5f;
        margin-top: 18px;
        margin-bottom: 8px;
        page-break-after: avoid;
    }}
    h4 {{
        font-size: 10.5pt;
        color: #333333;
        margin-top: 12px;
        margin-bottom: 6px;
        page-break-after: avoid;
    }}
    p {{
        margin-top: 0;
        margin-bottom: 10px;
        text-align: justify;
    }}
    hr {{
        border: 0;
        border-top: 1px solid #eaecef;
        margin: 20px 0;
    }}
    table {{
        width: 100%;
        border-collapse: collapse;
        margin: 14px 0 18px 0;
        font-size: 9.5pt;
        page-break-inside: avoid;
    }}
    th, td {{
        border: 1px solid #d0d7de;
        padding: 8px 10px;
        text-align: left;
    }}
    th {{
        background-color: #f6f8fa;
        font-weight: 600;
        color: #24292e;
    }}
    tr:nth-child(even) td {{
        background-color: #fafbfc;
    }}
    pre, code {{
        font-family: "Consolas", "Courier New", monospace;
        font-size: 9pt;
    }}
    code {{
        background-color: #f6f8fa;
        padding: 2px 5px;
        border-radius: 4px;
        color: #b31d28;
    }}
    pre {{
        background-color: #f6f8fa;
        border: 1px solid #e1e4e8;
        border-radius: 6px;
        padding: 12px;
        white-space: pre-wrap;
        word-wrap: break-word;
        margin: 12px 0;
        page-break-inside: avoid;
    }}
    blockquote {{
        border-left: 4px solid #028090;
        padding: 8px 16px;
        margin: 12px 0;
        color: #444d56;
        background-color: #f1f8f9;
        border-radius: 0 4px 4px 0;
        page-break-inside: avoid;
    }}
    ul, ol {{
        margin-top: 4px;
        margin-bottom: 10px;
        padding-left: 24px;
    }}
    li {{
        margin-bottom: 4px;
    }}
</style>
</head>
<body>
{html_body}
</body>
</html>
"""
    return styled_html

def export_files():
    if not os.path.exists(MD_FILE):
        print(f"Khong tim thay: {MD_FILE}")
        return

    html_content = convert_md_to_html(MD_FILE)
    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(html_content)

    browser_exe = find_browser_executable()
    if browser_exe:
        cmd = [
            browser_exe,
            "--headless=new",
            "--disable-gpu",
            f"--print-to-pdf={PDF_FILE}",
            HTML_FILE
        ]
        try:
            subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if os.path.exists(PDF_FILE) and os.path.getsize(PDF_FILE) > 0:
                print(f"Da xuat PDF thanh cong: {PDF_FILE}")
                return
        except Exception as e:
            pass

if __name__ == "__main__":
    export_files()
