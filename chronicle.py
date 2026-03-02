import os
import platform
import time
import json
import re
import cv2
from PIL import Image
from pypdf import PdfReader, PdfWriter
import docx
from fpdf import FPDF
from google import genai
import logging
import shutil
import openpyxl
from ebooklib import epub
import textwrap
import sys
import glob

# Dynamically link Homebrew's Python site-packages for Mac users
brew_paths = glob.glob("/opt/homebrew/lib/python3.*/site-packages") + glob.glob("/usr/local/lib/python3.*/site-packages")
for path in brew_paths:
    if os.path.exists(path) and path not in sys.path:
        sys.path.append(path)

try:
    import louis
except ImportError:
    louis = None

logging.getLogger("pypdf").setLevel(logging.ERROR)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_DIR = os.path.join(SCRIPT_DIR, "input_files")
BATCH_INPUT_DIR = os.path.join(SCRIPT_DIR, "Input_Scans")
KEY_FILE = os.path.join(SCRIPT_DIR, "api_key.txt")
CONFIG_FILE = os.path.join(SCRIPT_DIR, "user_config.json")

PDF_CHUNK_PAGES = 5
TEXT_CHUNK_CHARS = 15000 
SUPPORTED_EXTENSIONS = ['.pdf', '.docx', '.txt', '.md', '.rtf', '.csv', '.js', '.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.webp', '.xlsx']

def get_api_key():
    if os.path.exists(KEY_FILE):
        with open(KEY_FILE, "r") as f:
            key = f.read().strip()
            if key: return key
    print("\nFIRST TIME SETUP")
    new_key = input("Please paste your Google Gemini API Key here and press Enter: ").strip()
    if new_key:
        with open(KEY_FILE, "w") as f: f.write(new_key)
        return new_key
    exit()

def get_brf_table():
    config = {}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
            if "brf_table" in config: return config["brf_table"]
    
    print("\nBRAILLE READY FORMAT (BRF) SETUP")
    options = ["1. UEB Grade 2 (Default)", "2. UEB Grade 1", "3. US English", "4. UK English", "5. Custom Table"]
    for o in options: print(o)
    
    choice = input("Select Standard (1-5): ").strip()
    table = "en-ueb-g2.ctb"
    if choice == '2': table = "en-ueb-g1.ctb"
    elif choice == '3': table = "en-us-g2.ctb"
    elif choice == '4': table = "en-gb-g2.ctb"
    elif choice == '5': table = input("Enter exact table name (e.g., fr-bfu-comp8.utb): ").strip()
    
    config["brf_table"] = table
    with open(CONFIG_FILE, "w") as f: json.dump(config, f)
    return table

def ask_menu(title, options, option_map, default_key=''):
    print(f"\n{title}")
    for opt in options: print(opt)
    while True:
        choice = input("Select option: ").strip()
        if choice in option_map: return option_map[choice]
        if choice == '' and default_key in option_map: return option_map[default_key]
        print("Invalid choice.")

def ask_bool(title, options, true_choice='2'):
    print(f"\n{title}")
    for opt in options: print(opt)
    while True:
        choice = input("Select option: ").strip()
        if choice == true_choice: return True
        if choice in ['0', '1', '']: return False
        print("Invalid choice.")

def get_user_preferences():
    config = {}
    
    fmt_options = ["1. HTML", "2. TXT", "3. DOCX", "4. MD", "5. PDF", "6. JSON", "7. CSV", "8. EPUB", "9. BRF"]
    fmt_map = {
        '1': ('html', 'output_html'), '2': ('txt', 'output_txt'), '3': ('docx', 'output_docx'),
        '4': ('md', 'output_md'), '5': ('pdf', 'output_pdf'), '6': ('json', 'output_json'),
        '7': ('csv', 'output_csv'), '8': ('epub', 'output_epub'), '9': ('brf', 'output_brf')
    }
    fmt, out_folder = ask_menu("MENU 1: OUTPUT FORMAT", fmt_options, fmt_map)
    
    if fmt == 'brf' and louis is None:
        print("WARNING: Liblouis not installed. Falling back to TXT.")
        fmt, out_folder = 'txt', 'output_txt'
        
    config['format_type'] = fmt
    config['output_dir'] = os.path.join(SCRIPT_DIR, out_folder)
    if fmt == 'brf': config['brf_table'] = get_brf_table()

    config['model_name'] = ask_menu("MENU 2: AI ENGINE", ["1. Standard (Flash)", "2. Deep Scan (Pro)"], {'1':'gemini-2.5-flash', '2':'gemini-2.5-pro', '':'gemini-2.5-flash'}, '')
    config['translate_mode'] = ask_menu("MENU 3: TRANSLATION", ["0. Skip", "2. Translate (Keep original)", "3. Translate (Discard original)"], {'0':'none', '1':'none', '2':'both', '3':'english_only', '':'none'}, '')
    config['modernize_punctuation'] = ask_bool("MENU 4: PUNCTUATION", ["0. Skip", "2. Modernize"])
    config['condition_profiling'] = ask_bool("MENU 5: CONDITION PROFILING", ["0. Skip", "2. Enable"])
    config['unit_conversion'] = ask_bool("MENU 6: UNIT CONVERSION", ["0. Skip", "2. Convert"])
    config['merge_files'] = ask_bool("MENU 7: FILE HANDLING", ["0. Process individually", "2. Merge files"])
    
    img_choice = ask_menu("MENU 8: VISUAL DESCRIPTIONS", ["0. Enable (Default)", "1. Disable"], {'0':True, '1':False, '2':True, '':True}, '')
    config['image_descriptions'] = img_choice
    
    config['batch_mode'] = ask_menu("MENU 9: BATCH SCANNING", ["0. Standard scan", "1. Recursive (Keep)", "2. Recursive (Delete)"], {'0':'flat', '1':'recursive_keep', '2':'recursive_delete', '':'flat'}, '')
    config['include_appendix'] = ask_bool("MENU 10: TECHNICAL APPENDIX", ["0. Exclude", "2. Include"])
    config['academic_mode'] = ask_bool("MENU 11: ACADEMIC ENGINE", ["0. Standard", "2. Enable"])
    config['toc_mode'] = ask_bool("MENU 12: AUTO-LINKING TOC", ["0. Disable", "2. Enable"])
    config['flatten_headers'] = ask_bool("MENU 13: HEADER FLATTENING", ["0. Keep verbatim", "2. Flatten"])
    
    return config

def get_prompt(config):
    if config['include_appendix']:
        metadata_rules = "- [Transcription Confidence: X/10]\n       - [Date: Month DD, YYYY]"
        if config['condition_profiling']: metadata_rules += "\n       - [Physical Condition]"
        appendix_rule = f"1. Metadata Appendix: Create a 'TECHNICAL APPENDIX' at the bottom:\n       {metadata_rules}"
    else:
        appendix_rule = "1. Seamless Reading Mode: Output ONLY the transcription. NO metadata appendices."

    unit_rule = "Convert historical measurements/currency in brackets." if config['unit_conversion'] else "Do not convert measurements."
    translate_rule = "Do not translate." if config['translate_mode'] == 'none' else "Translate to English, keep original in brackets." if config['translate_mode'] == 'both' else "Translate to English, discard original."
    punct_rule = "Modernize punctuation for rhythm." if config['modernize_punctuation'] else "Maintain exact original punctuation."
    image_rule = "Describe images in brackets [Image Description: ...]. Use <img alt=\"\"> in HTML if toggled off." if config['image_descriptions'] else "Ignore all images. If using HTML, use <img alt=\"\">."
    flatten_rule = "Header Flattening: Strip repetitive page numbers and security stamps. Stitch broken sentences together." if config['flatten_headers'] else "Preserve all headers and footers exactly."

    wcag_rules = "WCAG 2.2 COMPLIANCE: Use strict semantic HTML heading hierarchies (H1, H2). NEVER skip levels. Tables MUST use <th> and scope=\"col\"/row."
    academic_rules = "ACADEMIC RULES: Convert math to LaTeX. Group footnotes at the bottom. Preserve indigenous languages (e.g. Māori macrons) and ancient scripts (Hieroglyphs). If HTML, wrap in <span lang=\"x\">." if config['academic_mode'] else ""
    toc_rules = "TABLE OF CONTENTS: Create internal HTML anchor links for all chapters." if config['toc_mode'] else ""
    anti_hallucinate = "ANTI-HALLUCINATION: If text is degraded or microscopic, NEVER guess. Output [Illegible Micro-text: approx X words]."

    base_rules = f"""
    CRITICAL RULES:
    {appendix_rule}
    {anti_hallucinate}
    - Extract legal structures strictly.
    - Describe device schematics sequentially.
    - Read strikethroughs: [Struck through: text].
    - Flatten forms and checkboxes linearly.
    
    TOGGLES:
    - {unit_rule}
    - {translate_rule}
    - {punct_rule}
    - {image_rule}
    - {flatten_rule}
    {wcag_rules}
    {academic_rules}
    {toc_rules}
    """
    
    fmt = config['format_type']
    if fmt == 'html': return f"Format strictly as HTML. No markdown wrappers. No body/html tags.\n{base_rules}"
    elif fmt == 'md': return f"Format as strict Markdown.\n{base_rules}"
    elif fmt == 'json': return f"Format as valid JSON.\n{base_rules}"
    elif fmt == 'csv': return f"Format as valid CSV.\n{base_rules}"
    elif fmt == 'epub': return f"Format as semantic HTML for EPUB processing.\n{base_rules}"
    elif fmt == 'pdf': return f"Format as semantic HTML. This will be compiled into a PDF.\n{base_rules}"
    elif fmt == 'brf': return f"Format strictly as plain text with standard spacing. NO markdown. NO HTML. This will be translated directly to Braille.\n{base_rules}"
    else: return f"Format as plain text.\n{base_rules}"
def enhance_image_for_microtext(file_path):
    try:
        img = cv2.imread(file_path)
        if img is None: return file_path
        width, height = int(img.shape[1] * 2), int(img.shape[0] * 2)
        resized = cv2.resize(img, (width, height), interpolation=cv2.INTER_LANCZOS4)
        gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
        temp_path = file_path + "_enhanced.png"
        cv2.imwrite(temp_path, gray)
        return temp_path
    except Exception as e:
        print(f"Warning: Could not enhance image ({e}). Using original.")
        return file_path

def clean_text_artifacts(text):
    if not text: return ""
    replacements = {"â€™": "'", "â€œ": '"', "â€": '"', "â€“": "-", "â€”": "-", "’": "'", "‘": "'", "“": '"', "”": '"', "–": "-", "—": "-", "Â\xa0": " ", "Â": ""}
    for old, new in replacements.items(): text = text.replace(old, new)
    return text

def write_header(file_obj, title, format_type):
    if format_type == 'html':
        file_obj.write(f"<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n<title>{title}</title>\n</head>\n<body>\n")
        file_obj.flush()

def write_footer(file_obj, format_type):
    if format_type == 'html':
        file_obj.write("\n</body>\n</html>")
        file_obj.flush()

def save_as_pdf(pdf_path, text_content):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("Helvetica", size=11)
    safe_text = text_content.encode('latin-1', 'replace').decode('latin-1')
    try:
        pdf.write_html(safe_text)
        pdf.output(pdf_path)
    except Exception as e:
        print(f"Warning: HTML-PDF compilation failed, falling back to flat text. {e}")
        pdf.multi_cell(0, 10, text=safe_text)
        pdf.output(pdf_path)

def append_to_docx(docx_path, text_content):
    doc = docx.Document(docx_path) if os.path.exists(docx_path) else docx.Document()
    for line in text_content.split('\n'):
        clean_line = line.strip()
        if clean_line.startswith('# '): doc.add_heading(clean_line[2:], level=1)
        elif clean_line.startswith('## '): doc.add_heading(clean_line[3:], level=2)
        elif clean_line.startswith('### '): doc.add_heading(clean_line[4:], level=3)
        elif clean_line.startswith('- ') or clean_line.startswith('* '): doc.add_paragraph(clean_line[2:], style='List Bullet')
        elif clean_line != "": doc.add_paragraph(clean_line)
    doc.save(docx_path)

def save_as_json(json_path, text_content):
    text_content = text_content.strip()
    if text_content.startswith("```json"): text_content = text_content[7:-3].strip()
    try: data = json.loads(text_content)
    except: data = {"chronicle_extracted_content": text_content}
    with open(json_path, 'w', encoding='utf-8') as f: json.dump(data, f, indent=4)

def save_as_csv(csv_path, text_content):
    text_content = text_content.replace("```csv", "").replace("```", "").strip()
    with open(csv_path, 'w', encoding='utf-8') as f: f.write(text_content)

def save_as_epub(epub_path, title, text_content):
    book = epub.EpubBook()
    book.set_identifier(f"chron_{int(time.time())}")
    book.set_title(title)
    book.set_language('en')
    
    chapters = re.split(r'(<h2.*?>.*?</h2>)', text_content, flags=re.IGNORECASE)
    epub_chapters, current_title, current_content, chap_idx = [], title, "", 1
    
    for segment in chapters:
        if segment.lower().startswith('<h2'):
            if current_content.strip():
                c = epub.EpubHtml(title=current_title, file_name=f'chap_{chap_idx}.xhtml', lang='en')
                c.content = f"<h1>{current_title}</h1><div>{current_content}</div>"
                epub_chapters.append(c)
                chap_idx += 1
            current_title = re.sub(r'<[^>]+>', '', segment)
            current_content = segment 
        else:
            current_content += segment
            
    if current_content.strip():
        c = epub.EpubHtml(title=current_title, file_name=f'chap_{chap_idx}.xhtml', lang='en')
        c.content = f"<h1>{current_title}</h1><div>{current_content}</div>"
        epub_chapters.append(c)

    for c in epub_chapters: book.add_item(c)
    book.spine = ['nav'] + epub_chapters
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    epub.write_epub(epub_path, book, {})

def save_as_brf(brf_path, text_content, table_name):
    if louis is None: return
    try:
        translated = louis.translateString([table_name], text_content)[0]
        lines = textwrap.wrap(translated, width=40)
        pages = ["\n".join(lines[i:i+25]) for i in range(0, len(lines), 25)]
        final_brf = "\n\x0C\n".join(pages) 
        with open(brf_path, 'a', encoding='utf-8') as f: f.write(final_brf + "\n")
    except Exception as e:
        print(f"Braille translation failed: {e}")

def dispatch_save(config, path, memory_list, title, clear_memory=False):
    """Centralized router that handles all advanced export formats."""
    content = "".join(memory_list)
    if not content: return
    fmt = config['format_type']
    
    if fmt == 'docx': 
        append_to_docx(path, content)
        if clear_memory: memory_list.clear()
    elif fmt == 'pdf': save_as_pdf(path, content)
    elif fmt == 'json': save_as_json(path, content)
    elif fmt == 'csv': save_as_csv(path, content)
    elif fmt == 'epub': save_as_epub(path, title, content)
    elif fmt == 'brf': 
        save_as_brf(path, content, config.get('brf_table'))
        if clear_memory: memory_list.clear()
def handle_stream(response, output_path, format_type, file_obj=None, memory_list=None):
    for chunk in response:
        if chunk.text:
            clean_chunk = clean_text_artifacts(chunk.text)
            if format_type in ['html', 'txt', 'md'] and file_obj:
                file_obj.write(clean_chunk)
                file_obj.flush()
            if memory_list is not None:
                memory_list.append(clean_chunk)

def play_completion_sound():
    print("\nProcessing complete!")
    if platform.system() == "Darwin": os.system('afplay /System/Library/Sounds/Glass.aiff')
    elif platform.system() == "Windows": os.system('PowerShell -Command "(New-Object Media.SoundPlayer \'C:\Windows\Media\notify.wav\').PlaySync();"')

def process_files():
    api_key = get_api_key()
    try: client = genai.Client(api_key=api_key)
    except Exception as e: return print(f"Connection Error: {e}")

    config = get_user_preferences()
    prompt_text = get_prompt(config)

    target_scan_dir = BATCH_INPUT_DIR if config['batch_mode'].startswith('recursive') else INPUT_DIR
    os.makedirs(target_scan_dir, exist_ok=True); os.makedirs(config['output_dir'], exist_ok=True)
    
    valid_files = []
    if config['batch_mode'].startswith('recursive'):
        for r, d, f in os.walk(target_scan_dir):
            valid_files.extend([os.path.join(r, file) for file in f if os.path.splitext(file)[1].lower() in SUPPORTED_EXTENSIONS and not file.startswith('.')])
    else:
        if os.path.exists(target_scan_dir):
            valid_files = [os.path.join(target_scan_dir, f) for f in os.listdir(target_scan_dir) if os.path.splitext(f)[1].lower() in SUPPORTED_EXTENSIONS and not f.startswith('.')]
    
    if not valid_files: return print("No valid files found.")

    master_path = os.path.join(config['output_dir'], f"Chronicle_Merged.{config['format_type']}")
    master_file_obj, master_memory = None, []
    
    if config['merge_files']:
        if os.path.exists(master_path): os.remove(master_path)
        if config['format_type'] in ['html', 'txt', 'md']:
            master_file_obj = open(master_path, 'w', encoding='utf-8')
            write_header(master_file_obj, "Chronicle Merged", config['format_type'])

    for file_path in sorted(valid_files):
        filename = os.path.basename(file_path)
        base_name, ext = os.path.splitext(filename)[0], os.path.splitext(filename)[1].lower()
        
        current_memory = []
        if config['merge_files']:
            output_path, active_write_path = master_path, master_path
            current_file_obj, current_memory = master_file_obj, master_memory
            if config['format_type'] == 'html': current_file_obj.write("<br>")
            elif config['format_type'] in ['txt', 'md']: current_file_obj.write("\n\n")
        else:
            output_path = os.path.join(config['output_dir'], f"{base_name}.{config['format_type']}")
            active_write_path = output_path + ".tmp"
            if os.path.exists(output_path): continue
            if os.path.exists(active_write_path): os.remove(active_write_path)
            
            current_file_obj = open(active_write_path, 'w', encoding='utf-8') if config['format_type'] in ['html', 'txt', 'md'] else None
            if current_file_obj: write_header(current_file_obj, base_name, config['format_type'])
        
        print(f"\nProcessing {filename}...")
        try:
            if ext == '.pdf': process_pdf(client, file_path, active_write_path, config['format_type'], prompt_text, config['model_name'], current_file_obj, current_memory)
            elif ext in ['.docx', '.txt', '.md', '.rtf', '.csv', '.js', '.xlsx']: process_text_document(client, file_path, active_write_path, ext, config['format_type'], prompt_text, config['model_name'], current_file_obj, current_memory)
            elif ext in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.webp']: process_image(client, file_path, active_write_path, config['format_type'], prompt_text, config['model_name'], current_file_obj, current_memory)
            
            if config['batch_mode'] == 'recursive_delete': os.remove(file_path)

            if not config['merge_files']:
                dispatch_save(config, active_write_path, current_memory, base_name)
                if current_file_obj: write_footer(current_file_obj, config['format_type']); current_file_obj.close()
                if os.path.exists(active_write_path): os.rename(active_write_path, output_path)
            else:
                # Incremental live-saving for merged files
                dispatch_save(config, master_path, master_memory, "Merged", clear_memory=True)

        except Exception as e:
            print(f"Error on {filename}: {e}")
            if current_file_obj and not config['merge_files']: current_file_obj.close()

    if config['merge_files']:
        dispatch_save(config, master_path, master_memory, "Merged", clear_memory=True)
        if master_file_obj: write_footer(master_file_obj, config['format_type']); master_file_obj.close()
    play_completion_sound()

def process_pdf(client, pdf_path, output_path, format_type, prompt_text, model_name, file_obj, memory_list):
    reader = PdfReader(pdf_path)
    for start_page in range(0, len(reader.pages), PDF_CHUNK_PAGES):
        end_page = min(start_page + PDF_CHUNK_PAGES, len(reader.pages))
        chunk_filename = os.path.join(SCRIPT_DIR, f"temp_{start_page}.pdf")
        writer = PdfWriter()
        for i in range(start_page, end_page): writer.add_page(reader.pages[i])
        with open(chunk_filename, "wb") as f: writer.write(f)

        uploaded = client.files.upload(file=chunk_filename)
        handle_stream(client.models.generate_content_stream(model=model_name, contents=[uploaded, prompt_text]), output_path, format_type, file_obj, memory_list)
        client.files.delete(name=uploaded.name); os.remove(chunk_filename)

def process_text_document(client, file_path, output_path, ext, format_type, prompt_text, model_name, file_obj, memory_list):
    full_text = ""
    if ext == '.docx': full_text = "\n".join([p.text for p in docx.Document(file_path).paragraphs])
    elif ext == '.xlsx':
        wb = openpyxl.load_workbook(file_path, data_only=True)
        for name in wb.sheetnames:
            full_text += f"\n[--- Tab: {name} ---]\n"
            for row in wb[name].iter_rows(values_only=True):
                if any(c for c in row if str(c).strip()): full_text += " | ".join([str(c) if c else "" for c in row]) + "\n"
    else: full_text = open(file_path, 'r', encoding='utf-8', errors='ignore').read()

    chunks, current = [], ""
    for p in full_text.split('\n'):
        if len(current) + len(p) > TEXT_CHUNK_CHARS and current: chunks.append(current); current = p + "\n"
        else: current += p + "\n"
    if current: chunks.append(current)

    for chunk in chunks:
        handle_stream(client.models.generate_content_stream(model=model_name, contents=[chunk, prompt_text]), output_path, format_type, file_obj, memory_list)

def process_image(client, file_path, output_path, format_type, prompt_text, model_name, file_obj, memory_list):
    enhanced_path = enhance_image_for_microtext(file_path)
    uploaded = client.files.upload(file=enhanced_path)
    handle_stream(client.models.generate_content_stream(model=model_name, contents=[uploaded, prompt_text]), output_path, format_type, file_obj, memory_list)
    client.files.delete(name=uploaded.name)
    if enhanced_path != file_path: os.remove(enhanced_path)

if __name__ == "__main__":
    process_files()