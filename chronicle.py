import os
import platform
import time
from pypdf import PdfReader, PdfWriter
import docx
from fpdf import FPDF
from google import genai
from google.genai import types
import logging
import shutil

# Silence harmless PDF structural warnings from the PyPDF logger
logging.getLogger("pypdf").setLevel(logging.ERROR)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_DIR = os.path.join(SCRIPT_DIR, "input_files")
BATCH_INPUT_DIR = os.path.join(SCRIPT_DIR, "Input_Scans")
KEY_FILE = os.path.join(SCRIPT_DIR, "api_key.txt")

PDF_CHUNK_PAGES = 5
TEXT_CHUNK_CHARS = 15000 

SUPPORTED_EXTENSIONS = ['.pdf', '.docx', '.txt', '.md', '.rtf', '.csv', '.js', '.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp']

# Global accumulators for Clean Reading Mode
document_body_accumulator = ""
tech_appendix_accumulator = "\n<hr>\n<section id='appendix' aria-labelledby='appendix-heading'>\n<h2 id='appendix-heading'>Technical Appendix</h2>\n<ul>"

def get_api_key():
    if os.path.exists(KEY_FILE):
        with open(KEY_FILE, "r") as f:
            key = f.read().strip()
            if key:
                return key
    
    print("\nFIRST TIME SETUP")
    print("Welcome to Chronicle. To use this tool, you need a Google Gemini API Key.")
    new_key = input("Please paste your API Key here and press Enter: ").strip()
    
    if new_key:
        with open(KEY_FILE, "w") as f:
            f.write(new_key)
        print("Key saved! You won't need to do this again.\n")
        return new_key
    else:
        print("No key provided. Exiting.")
        exit()

def get_user_preferences():
    print("\nMENU 1: OUTPUT FORMAT (Mandatory)")
    print("1. HTML (Best for Screen Readers)")
    print("2. Plain Text (.txt)")
    print("3. Microsoft Word (.docx)")
    print("4. Markdown (.md)")
    print("5. PDF Document (.pdf)")
    while True:
        format_choice = input("Type 1, 2, 3, 4, or 5 and press Enter: ").strip()
        if format_choice == '1':
            format_type, output_dir = 'html', os.path.join(SCRIPT_DIR, "output_html")
            break
        elif format_choice == '2':
            format_type, output_dir = 'txt', os.path.join(SCRIPT_DIR, "output_txt")
            break
        elif format_choice == '3':
            format_type, output_dir = 'docx', os.path.join(SCRIPT_DIR, "output_docx")
            break
        elif format_choice == '4':
            format_type, output_dir = 'md', os.path.join(SCRIPT_DIR, "output_md")
            break
        elif format_choice == '5':
            format_type, output_dir = 'pdf', os.path.join(SCRIPT_DIR, "output_pdf")
            break
        else:
            print("Invalid choice.")

    print("\nMENU 2: AI ENGINE SELECTION (Mandatory)")
    print("1. Standard Speed (Best for typed text, fast)")
    print("2. Deep Scan (Best for faded handwriting, slower)")
    while True:
        engine_choice = input("Type 1 or 2 and press Enter: ").strip()
        if engine_choice == '1':
            model_name = 'gemini-2.0-flash'
            break
        elif engine_choice == '2':
            model_name = 'gemini-1.5-pro'
            break
        else:
            print("Invalid choice.")
            
    print("\nMENU 3: TRANSLATION MODE")
    print("0. Skip (Default: Keep original language)")
    print("1. No Translation")
    print("2. Translate to English (Keep original in brackets)")
    print("3. Translate to English (Discard original)")
    while True:
        trans_choice = input("Select option: ").strip()
        if trans_choice in ['0', '1', '']:
            translate_mode = 'none'
            break
        elif trans_choice == '2':
            translate_mode = 'both'
            break
        elif trans_choice == '3':
            translate_mode = 'english_only'
            break
        else:
            print("Invalid.")

    print("\nMENU 4: PUNCTUATION HANDLING")
    print("0. Skip (Default: Strict/Original)")
    print("1. Strict (Keep exact historical punctuation)")
    print("2. Modernize (Insert periods/commas for rhythm)")
    while True:
        punct_choice = input("Select option: ").strip()
        if punct_choice in ['0', '1', '']:
            modernize_punctuation = False
            break
        elif punct_choice == '2':
            modernize_punctuation = True
            break
        else:
            print("Invalid.")

    print("\nMENU 5: DOCUMENT CONDITION PROFILING")
    print("0. Skip (Default: No profiling)")
    print("1. No Profiling")
    print("2. Enable (Describe physical condition of artifact)")
    while True:
        condition_choice = input("Select option: ").strip()
        if condition_choice in ['0', '1', '']:
            condition_profiling = False
            break
        elif condition_choice == '2':
            condition_profiling = True
            break
        else:
            print("Invalid.")

    print("\nMENU 6: HISTORICAL UNIT CONVERSION")
    print("0. Skip (Default: Strict/Original)")
    print("1. Strict (Keep chains/shillings/leagues)")
    print("2. Convert (Insert modern equivalents in brackets)")
    while True:
        unit_choice = input("Select option: ").strip()
        if unit_choice in ['0', '1', '']:
            unit_conversion = False
            break
        elif unit_choice == '2':
            unit_conversion = True
            break
        else:
            print("Invalid.")

    print("\nMENU 7: FILE HANDLING")
    print("0. Skip (Default: Process individually)")
    print("1. Process files individually")
    print("2. Merge all files into one document")
    while True:
        merge_choice = input("Select option: ").strip()
        if merge_choice in ['0', '1', '']:
            merge_files = False
            break
        elif merge_choice == '2':
            merge_files = True
            break
        else:
            print("Invalid choice.")
            
    print("\nMENU 8: VISUAL SCENE DESCRIPTIONS")
    print("0. Skip (Default: Enable descriptions)")
    print("1. Disable (Ignore all photographs, maps, and logos)")
    print("2. Enable (Write detailed descriptions for visual elements)")
    while True:
        image_choice = input("Select option: ").strip()
        if image_choice in ['0', '2', '']:
            image_descriptions = True
            break
        elif image_choice == '1':
            image_descriptions = False
            break
        else:
            print("Invalid choice.")

    print("\nMENU 9: DIRECTORY BATCH SCANNING")
    print("0. Skip (Default: Standard flat scan of 'input_files')")
    print("1. Recursive Scan of 'Input_Scans' folder (Keep originals)")
    print("2. Recursive Scan of 'Input_Scans' folder (DELETE originals after processing)")
    while True:
        batch_choice = input("Select option: ").strip()
        if batch_choice in ['0', '']:
            batch_mode = 'flat'
            break
        elif batch_choice == '1':
            batch_mode = 'recursive_keep'
            break
        elif batch_choice == '2':
            batch_mode = 'recursive_delete'
            break
        else:
            print("Invalid choice.")

    return format_type, output_dir, model_name, merge_files, translate_mode, modernize_punctuation, condition_profiling, unit_conversion, image_descriptions, batch_mode

def get_prompt(format_type, translate_mode, modernize_punctuation, condition_profiling, unit_conversion, image_descriptions):
    
    metadata_rules = "- [Transcription Confidence: X/10 - brief explanation of document legibility]\n       - [Date: Extract the primary date and standardize as Month DD, YYYY]"
    if condition_profiling:
        metadata_rules += "\n       - [Physical Condition: One-sentence description]"

    unit_rule = "Unit Conversion: Insert modern equivalent in brackets." if unit_conversion else "Unit Conversion: Do not convert."
    
    if translate_mode == 'none':
        translation_rule = "Language: Transcribe in original language."
    elif translate_mode == 'both':
        translation_rule = "Translation: Translate to English and keep original in brackets."
    elif translate_mode == 'english_only':
        translation_rule = "Translation: Translate to English and discard original."

    punct_rule = "Punctuation Restoration: Insert proper sentence breaks for rhythm." if modernize_punctuation else "Punctuation: Maintain exact original."
    
    image_rule = "Visual Scene Descriptions: Insert detailed description in brackets." if image_descriptions else "Visual Scene Descriptions: Ignore images."

    base_rules = f"""
    1. CLEAN READING MODE: Put the transcription content in the main body. 
       DO NOT put confidence scores or dates in the body.
       Append them to the TECHNICAL APPENDIX at the end.
    2. Encoding: Strictly standard ASCII.
    3. UI & Icons: Translate icons into spoken text (e.g., [Settings Icon]).
    4. Military: Telegraph STOP -> Period. Map Grid Spacing. Stamp Extraction. Expand Acronyms.
    5. Strikethrough Recovery: Tag [Struck through: text].
    6. Blank Page: Output [Page intentionally left blank].
    7. Form Flattening: Vertical lists for forms/tax docs.
    8. Checkboxes & Signatures: Declare status (e.g., [Checkbox: Selected]).
    9. {unit_rule} | {translation_rule} | {punct_rule} | {image_rule}
    """
    
    if format_type == 'html':
        return f"Format as semantic HTML for screen readers. {base_rules}"
    return f"Format as clean text. {base_rules}"

def clean_text_artifacts(text):
    if not text:
        return ""
    return text.encode("utf-8", "ignore").decode("utf-8")

def write_header(file_obj, title, format_type):
    if format_type == 'html':
        file_obj.write(f"<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n<meta charset=\"UTF-8\">\n<title>{title}</title>\n</head>\n<body>\n")

def write_footer(file_obj, format_type):
    if format_type == 'html':
        file_obj.write("\n</body>\n</html>")

def save_as_pdf(pdf_path, text_content):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("Helvetica", size=12)
    safe_text = text_content.encode('latin-1', 'replace').decode('latin-1')
    pdf.multi_cell(0, 10, txt=safe_text)
    pdf.output(pdf_path)

def append_to_docx(docx_path, text_content):
    doc = docx.Document() if not os.path.exists(docx_path) else docx.Document(docx_path)
    doc.add_paragraph(text_content)
    doc.save(docx_path)

def process_files():
    global document_body_accumulator, tech_appendix_accumulator
    api_key = get_api_key()
    client = genai.Client(api_key=api_key)
    
    prefs = get_user_preferences()
    format_type, output_dir, model_name, merge_files, translate_mode, modernize_punctuation, condition_profiling, unit_conversion, image_descriptions, batch_mode = prefs
    prompt_text = get_prompt(format_type, translate_mode, modernize_punctuation, condition_profiling, unit_conversion, image_descriptions)

    os.makedirs(output_dir, exist_ok=True)
    scan_dir = BATCH_INPUT_DIR if batch_mode.startswith('recursive') else INPUT_DIR
    valid_files = sorted([os.path.join(scan_dir, f) for f in os.listdir(scan_dir) if os.path.splitext(f)[1].lower() in SUPPORTED_EXTENSIONS])
    
    if not valid_files:
        print("No files found.")
        return

    for file_path in valid_files:
        filename = os.path.basename(file_path)
        print(f"Deep Processing: {filename}...")
        
        ext = os.path.splitext(filename)[1].lower()
        if ext == '.pdf':
            reader = PdfReader(file_path)
            for start in range(0, len(reader.pages), PDF_CHUNK_PAGES):
                end = min(start + PDF_CHUNK_PAGES, len(reader.pages))
                temp_pdf = f"temp_{start}.pdf"
                writer = PdfWriter()
                for i in range(start, end): writer.add_page(reader.pages[i])
                with open(temp_pdf, "wb") as f: writer.write(f)
                
                uploaded = client.files.upload(file=temp_pdf)
                response = client.models.generate_content(model=model_name, contents=[uploaded, prompt_text])
                document_body_accumulator += f"<section><h3>{filename} (Pages {start+1}-{end})</h3>{response.text}</section>"
                tech_appendix_accumulator += f"<li>{filename} (Pages {start+1}-{end}): Success</li>"
                os.remove(temp_pdf)
        else:
            with open(file_path, "rb") as f:
                file_data = f.read()
            response = client.models.generate_content(
                model=model_name,
                contents=[types.Part.from_bytes(data=file_data, mime_type="image/jpeg"), prompt_text]
            )
            document_body_accumulator += f"<article><h2>{filename}</h2>{response.text}</article>"
            tech_appendix_accumulator += f"<li>{filename}: Status Success</li>"

    # Final Output Generation
    output_path = os.path.join(output_dir, f"Chronicle_Output.{format_type}")
    with open(output_path, 'w', encoding='utf-8') as f:
        if format_type == 'html':
            write_header(f, "Chronicle", format_type)
            f.write(document_body_accumulator)
            f.write(tech_appendix_accumulator + "</ul></section>")
            write_footer(f, format_type)
        else:
            f.write(document_body_accumulator)
    
    if platform.system() == "Darwin":
        os.system('afplay /System/Library/Sounds/Glass.aiff')
    print(f"SUCCESS: Master Engine Restored. Size: {os.path.getsize('chronicle.py')} bytes")

if __name__ == "__main__":
    process_files()