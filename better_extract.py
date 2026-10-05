import zipfile
import xml.etree.ElementTree as ET
import sys
import os

path = "Project Title.docx"

def get_text(filename):
    try:
        with zipfile.ZipFile(path) as docx:
            tree = ET.XML(docx.read(filename))
            
        text_content = []
        ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        
        for paragraph in tree.findall('.//w:p', ns):
            para_text = []
            for node in paragraph.iter():
                if node.tag.endswith('t'):
                    if node.text:
                        para_text.append(node.text)
                elif node.tag.endswith('br'):
                    para_text.append('\n')
                elif node.tag.endswith('cr'):
                    para_text.append('\n')
            if para_text:
                text_content.append(''.join(para_text))
        return '\n'.join(text_content)
    except KeyError:
        return ""
    except Exception as e:
        return f"Error: {e}"

print("--- DOCUMENT BODY ---")
print(get_text('word/document.xml'))
print("\n--- HEADERS ---")
# Try to find headers
try:
    with zipfile.ZipFile(path) as docx:
        for name in docx.namelist():
            if name.startswith('word/header'):
                print(f"[{name}]:")
                print(get_text(name))
except:
    pass
