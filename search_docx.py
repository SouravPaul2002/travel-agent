import zipfile
import re

path = "Project Title.docx"
search_term = "langchain"

try:
    with zipfile.ZipFile(path) as docx:
        # Read the main document body
        if 'word/document.xml' in docx.namelist():
            xml_content = docx.read('word/document.xml').decode('utf-8')
            # Remove XML tags to search in text
            text_content = re.sub(r'<[^>]+>', '', xml_content)
            
            if search_term.lower() in text_content.lower():
                print(f"FOUND: '{search_term}' was found in the document.")
                # Show context
                idx = text_content.lower().find(search_term.lower())
                start = max(0, idx - 50)
                end = min(len(text_content), idx + 50)
                print(f"Context: ...{text_content[start:end]}...")
            else:
                print(f"NOT FOUND: '{search_term}' was NOT found in the document.")
                
        else:
            print("Error: word/document.xml not found")
            
except Exception as e:
    print(f"Error: {e}")
