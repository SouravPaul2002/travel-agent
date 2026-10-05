import zipfile
import re

path = "Project Title.docx"

try:
    with zipfile.ZipFile(path) as docx:
        xml_content = docx.read('word/document.xml').decode('utf-8')
        # Find all text inside <w:t> tags
        matches = re.findall(r'<w:t[^>]*>(.*?)</w:t>', xml_content)
        full_text = "".join(matches)
        print(full_text)
except Exception as e:
    print(f"Error: {e}")
