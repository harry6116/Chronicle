import os
import platform
import time
from pypdf import PdfReader, PdfWriter
import docx
from fpdf import FPDF
from google import genai
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
            model_name = 'gemini-2.5-flash'
            break
        elif engine_choice == '2':
            model_name = 'gemini-2.5-pro'
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
    print("2. Merge all files into one seamless document")
    while True:
        merge_choice = input("Select option: ").strip()
        if merge_choice in ['0', '1', '']:
            merge_files = False
            break
        elif merge_choice == '2':
            merge_files = True
            break
        else:
            print("Invalid.")
            
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
            print("Invalid.")

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

    print("\nMENU 10: TECHNICAL APPENDIX (Metadata & Confidence Scores)")
    print("0. Skip (Default: Exclude for seamless reading)")
    print("1. Exclude completely (Best for continuous letters)")
    print("2. Include at the bottom of each page")
    while True:
        app_choice = input("Select option: ").strip()
        if app_choice in ['0', '1', '']:
            include_appendix = False
            break
        elif app_choice == '2':
            include_appendix = True
            break
        else:
            print("Invalid choice.")

    return format_type, output_dir, model_name, merge_files, translate_mode, modernize_punctuation, condition_profiling, unit_conversion, image_descriptions, batch_mode, include_appendix

def get_prompt(format_type, translate_mode, modernize_punctuation, condition_profiling, unit_conversion, image_descriptions, include_appendix):
    
    if include_appendix:
        metadata_rules = "- [Transcription Confidence: X/10 - brief explanation of document legibility]\n       - [Date: Extract the primary date of the document/entry and standardize it as Month DD, YYYY. If none, write Unknown]"
        if condition_profiling:
            metadata_rules += "\n       - [Physical Condition: A one-sentence description of the artifact's visual state, e.g., faded ink, water damage]"
        appendix_rule = f"1. Metadata Appendix: Do NOT put the Document Metadata at the top. Create a 'TECHNICAL APPENDIX' at the very bottom of your response and place the following tags there:\n       {metadata_rules}"
    else:
        appendix_rule = "1. Seamless Reading Mode: Output ONLY the transcription and visual descriptions. DO NOT generate any confidence scores, dates, condition profiles, or technical appendices."

    unit_rule = "Unit Conversion: If you encounter outdated historical measurements or currency (e.g., chains, shillings, leagues), quietly insert the modern equivalent in brackets." if unit_conversion else "Unit Conversion: Do not convert any historical measurements or currency. Keep them exactly as written."
    
    if translate_mode == 'none':
        translation_rule = "Language: Transcribe the text exactly in its original language. Do not translate."
    elif translate_mode == 'both':
        translation_rule = "Translation: If you detect text in a language other than English, translate it into English. Immediately follow the translated sentence with the original foreign text in square brackets."
    elif translate_mode == 'english_only':
        translation_rule = "Translation: If you detect text in a language other than English, translate it entirely into English. Discard the original foreign text completely."

    punct_rule = "Punctuation Restoration: Insert proper sentence breaks, periods, and commas where they are missing to create a smooth reading rhythm. Do not change actual words." if modernize_punctuation else "Punctuation: Maintain the exact original punctuation. Do not add missing periods or commas."
    
    image_rule = "Visual Scene Descriptions: If the document contains any photographs, maps, diagrams, or illustrations, insert a detailed visual description of the image enclosed in square brackets, formatted exactly like this: [Image Description: a brief, highly descriptive explanation]." if image_descriptions else "Visual Scene Descriptions: Ignore all photographs, maps, diagrams, logos, and illustrations. Do not describe them."

    base_rules = f"""
    CRITICAL OCR, HANDWRITING, AND ACCESSIBILITY RULES:
    
    {appendix_rule}
    2. Encoding Safety: Use strictly standard ASCII punctuation for quotes and dashes. Do NOT use 'smart' curly quotes, long em-dashes, or non-breaking spaces.
    
    TECHNICAL MANUALS & DEVICE GUIDES:
    3. UI & Button Translation: If processing an instruction manual, translate all inline visual icons, button pictures, and interface symbols into clear spoken text (e.g., replace a picture of a gear with [Settings Icon], or a triangle with [Play Button]). NEVER skip a visual step.
    4. Device Schematics: If a diagram points out parts of a device using numbers or lines, extract it into a linear, descriptive list mapping the device spatially (e.g., [Part 1: Power Button - located on top right edge]).
    
    MILITARY & ARCHIVAL INTELLIGENCE:
    5. Telegraph & Cablegram Decoder: If the document is a telegram using the word "STOP" for punctuation, replace "STOP" with a standard period and a paragraph break.
    6. Map Grid References: Format military map coordinates with spaced digits (e.g., [Map Grid Reference: 1 2 3 - 4 5 6]).
    7. Nominal Rolls & Casualty Lists: Rebuild densely packed lists of soldiers into strict, cleanly scoped tables to maintain structural orientation.
    8. Security Classifications: Extract stamps (e.g., TOP SECRET) and place them at the very top of the output as [Document Classification: TOP SECRET].
    9. Chain of Command Header Parsing: Isolate military routing blocks (FM:, TO:), expand acronyms, and place them cleanly at the top.
    10. Strikethrough Recovery: Do not skip crossed-out text. Read it and tag it (e.g., [Struck through: original text]).
    11. Official Seals & Watermarks: Look for and describe physical authentication marks (e.g., [Official Embossed Seal]).
    12. Visual Emphasis: Translate visual intent for heavily underlined/capitalized text (e.g., [Emphasis: IMMEDIATE ACTION]).
    13. Shorthand Detection: Flag untranscribable shorthand (e.g., [Visual Note: Untranscribed shorthand]).
    14. Blank Page Detection: If a page is entirely empty or only contains smudges, output exactly: [Page intentionally left blank].
    15. Redaction Tagging: If text is deliberately blacked out, insert the tag: [Text Redacted by Censor].
    16. Article Separation: For multi-column newspapers, insert a clear [--- End of Article ---] break.
    17. Military Abbreviations: Expand acronyms into full spoken forms.
    
    MODERN BUSINESS & CODE RULES:
    18. Form Flattening: Extract rigid tax forms/applications into a clean, linear vertical list.
    19. Checkboxes: Declare the status of visual toggles (e.g., [Checkbox: Selected] or [Checkbox: Empty]).
    20. Signature Detection: Indicate if a signature block is signed or empty.
    21. Code Formatting: Cleanly extract programming code (.js files), preserving line breaks and indentation.
    
    DATA INTEGRITY:
    22. Illegible Text: Do not guess destroyed text. Insert [illegible: approx 3 words].
    23. Uncensored Transcription: Transcribe all profanity, slurs, and explicit language verbatim. Do NOT censor or asterisk.
    24. Text Integrity: Never summarize historical content.
    25. Marginalia: Tag scribbled margin notes clearly.
    
    DYNAMIC TOGGLES:
    26. {unit_rule}
    27. {translation_rule}
    28. {punct_rule}
    29. {image_rule}
    """
    
    if format_type == 'html':
        return f"Format the extracted text as well-structured HTML highly accessible for screen readers. Use proper heading tags, paragraphs, and lists. Construct proper HTML tables with scope attributes for headers. Do NOT include markdown block formatting. Do NOT include <html>, <head>, or <body> tags.\n{base_rules}"
    elif format_type == 'md':
        return f"Format the extracted text as clean, semantic Markdown. Use # for headings, standard bullet points, and markdown tables where appropriate.\n{base_rules}"
    else:
        return f"Extract and format the text as clean, readable plain text. Format tabular data cleanly using spaces, but do not use HTML or Markdown. Do NOT use markdown symbols like asterisks or hashes for formatting.\n{base_rules}"

def clean_text_artifacts(text):
    if not text:
        return ""
    
    replacements = {
        "â€™": "'", "â€œ": '"', "â€": '"', "â€“": "-", "â€”": "-", 
        "’": "'", "‘": "'", "“": '"', "”": '"', "–": "-", "—": "-", "…": "...",
        "Â\xa0": " ", "Â ": " ", "Â": ""
    }
    
    for old, new in replacements.items():
        text = text.replace(old, new)
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
    
    pdf.set_font("Helvetica", size=12)
    safe_text = text_content.encode('latin-1', 'replace').decode('latin-1')
    
    pdf.multi_cell(0, 10, txt=safe_text)
    try:
        pdf.output(pdf_path)
    except Exception as e:
        print(f"Error saving PDF (formatting issue): {e}")

def append_to_docx(docx_path, text_content):
    if os.path.exists(docx_path):
        doc = docx.Document(docx_path)
    else:
        doc = docx.Document()
    doc.add_paragraph(text_content)
    doc.save(docx_path)

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
    system_os = platform.system()
    if system_os == "Darwin":
        os.system('afplay /System/Library/Sounds/Glass.aiff')
    elif system_os == "Windows":
        os.system('PowerShell -Command "(New-Object Media.SoundPlayer \'C:\Windows\Media\notify.wav\').PlaySync();"')

def process_files():
    api_key = get_api_key()
    print("\nInitializing Gemini Client...")
    try:
        client = genai.Client(api_key=api_key)
    except Exception as e:
        print(f"Error: Could not connect. Details: {e}")
        return

    format_type, output_dir, model_name, merge_files, translate_mode, modernize_punctuation, condition_profiling, unit_conversion, image_descriptions, batch_mode, include_appendix = get_user_preferences()
    prompt_text = get_prompt(format_type, translate_mode, modernize_punctuation, condition_profiling, unit_conversion, image_descriptions, include_appendix)

    if batch_mode.startswith('recursive'):
        target_scan_dir = BATCH_INPUT_DIR
        print(f"\n--- BATCH MODE ACTIVE: Scanning {target_scan_dir} and subfolders ---")
    else:
        target_scan_dir = INPUT_DIR

    os.makedirs(target_scan_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)
    
    valid_files = []
    if batch_mode.startswith('recursive'):
        for root, dirs, files in os.walk(target_scan_dir):
            for f in files:
                if not f.startswith('.') and os.path.splitext(f)[1].lower() in SUPPORTED_EXTENSIONS:
                    valid_files.append(os.path.join(root, f))
        valid_files.sort()
    else:
        if os.path.exists(target_scan_dir):
            files = sorted([f for f in os.listdir(target_scan_dir) if not f.startswith('.')])
            for f in files:
                if os.path.splitext(f)[1].lower() in SUPPORTED_EXTENSIONS:
                    valid_files.append(os.path.join(target_scan_dir, f))
    
    if not valid_files:
        print(f"No valid files found in {target_scan_dir}. Supported formats: {', '.join(SUPPORTED_EXTENSIONS)}")
        return

    master_file_obj = None
    master_memory = []
    master_path = os.path.join(output_dir, f"Chronicle_Merged_Document.{format_type}")
    
    if merge_files:
        print("\n--- MERGE MODE ACTIVE ---")
        if format_type in ['docx', 'pdf'] and os.path.exists(master_path):
            os.remove(master_path)
        elif format_type in ['html', 'txt', 'md']:
            master_file_obj = open(master_path, 'w', encoding='utf-8')
            write_header(master_file_obj, "Chronicle Merged Document", format_type)

    for file_path in valid_files:
        filename = os.path.basename(file_path)
        base_name = os.path.splitext(filename)[0]
        ext = os.path.splitext(filename)[1].lower()
        
        current_memory = []
        
        if merge_files:
            output_path = master_path
            current_file_obj = master_file_obj
            current_memory = master_memory
            
            # Invisible stitching for seamless reading flow
            if format_type == 'html':
                current_file_obj.write(f"\n<br>\n")
            elif format_type in ['txt', 'md']:
                current_file_obj.write(f"\n\n")
            elif format_type in ['docx', 'pdf']:
                current_memory.append(f"\n\n")
        else:
            output_path = os.path.join(output_dir, f"{base_name}.{format_type}")
            if format_type in ['docx', 'pdf'] and os.path.exists(output_path):
                os.remove(output_path)
            
            current_file_obj = None
            if format_type in ['html', 'txt', 'md']:
                current_file_obj = open(output_path, 'w', encoding='utf-8')
                write_header(current_file_obj, base_name, format_type)
        
        print(f"\nAnalyzing {filename} using {model_name}...")
        
        try:
            if ext == '.pdf':
                process_pdf(client, file_path, output_path, format_type, prompt_text, model_name, current_file_obj, current_memory)
            elif ext in ['.docx', '.txt', '.md', '.rtf', '.csv', '.js']:
                process_text_document(client, file_path, output_path, ext, format_type, prompt_text, model_name, current_file_obj, current_memory)
            elif ext in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp']:
                process_image(client, file_path, output_path, format_type, prompt_text, model_name, current_file_obj, current_memory)
            
            if batch_mode == 'recursive_delete':
                try:
                    os.remove(file_path)
                    print(f"  -> [CLEANUP] Deleted original file: {filename}")
                except Exception as e:
                    print(f"  -> [CLEANUP WARNING] Could not delete {filename}: {e}")

        except Exception as e:
            print(f"Error processing {filename}: {e}")
            
        if not merge_files:
            if format_type == 'docx' and current_memory:
                append_to_docx(output_path, "".join(current_memory))
            elif format_type == 'pdf' and current_memory:
                save_as_pdf(output_path, "".join(current_memory))
                
            if current_file_obj:
                write_footer(current_file_obj, format_type)
                current_file_obj.close()
            print(f"Finished formatting {base_name}.")

    if merge_files:
        if format_type == 'docx' and master_memory:
            append_to_docx(master_path, "".join(master_memory))
        elif format_type == 'pdf' and master_memory:
            save_as_pdf(master_path, "".join(master_memory))
            
        if master_file_obj:
            write_footer(master_file_obj, format_type)
            master_file_obj.close()
        print(f"\nFinished merging all files into Chronicle_Merged_Document.{format_type}")

    play_completion_sound()

def process_pdf(client, pdf_path, output_path, format_type, prompt_text, model_name, file_obj, memory_list):
    reader = PdfReader(pdf_path)
    total_pages = len(reader.pages)
    print(f"PDF has {total_pages} pages. Splitting into chunks.")

    for start_page in range(0, total_pages, PDF_CHUNK_PAGES):
        end_page = min(start_page + PDF_CHUNK_PAGES, total_pages)
        chunk_filename = os.path.join(SCRIPT_DIR, f"temp_chunk_{start_page}_to_{end_page}.pdf")
        
        print(f"  -> Uploading pages {start_page + 1} to {end_page}...")
        writer = PdfWriter()
        for i in range(start_page, end_page):
            writer.add_page(reader.pages[i])
        
        with open(chunk_filename, "wb") as temp_pdf:
            writer.write(temp_pdf)

        uploaded_file = client.files.upload(file=chunk_filename)
        response = client.models.generate_content_stream(
            model=model_name, 
            contents=[uploaded_file, f"Extract text from this PDF chunk.\n{prompt_text}"]
        )
        handle_stream(response, output_path, format_type, file_obj, memory_list)
        
        client.files.delete(name=uploaded_file.name)
        os.remove(chunk_filename)

def process_text_document(client, file_path, output_path, ext, format_type, prompt_text, model_name, file_obj, memory_list):
    print(f"Extracting text locally from {ext} file for chunking...")
    full_text = ""
    if ext == '.docx':
        doc = docx.Document(file_path)
        full_text = "\n".join([p.text for p in doc.paragraphs])
    else: 
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            full_text = f.read()

    paragraphs = full_text.split('\n')
    chunks, current_chunk = [], ""
    for p in paragraphs:
        if len(current_chunk) + len(p) > TEXT_CHUNK_CHARS and current_chunk:
            chunks.append(current_chunk)
            current_chunk = p + "\n"
        else:
            current_chunk += p + "\n"
    if current_chunk:
        chunks.append(current_chunk)

    for i, chunk_text in enumerate(chunks):
        print(f"  -> Processing chunk {i + 1} of {len(chunks)}...")
        response = client.models.generate_content_stream(
            model=model_name, 
            contents=[chunk_text, f"Clean up and format this text chunk.\n{prompt_text}"]
        )
        handle_stream(response, output_path, format_type, file_obj, memory_list)

def process_image(client, file_path, output_path, format_type, prompt_text, model_name, file_obj, memory_list):
    print(f"  -> Uploading image to Gemini for text extraction...")
    uploaded_file = client.files.upload(file=file_path)
    response = client.models.generate_content_stream(
        model=model_name, 
        contents=[uploaded_file, f"Extract text from this image.\n{prompt_text}"]
    )
    handle_stream(response, output_path, format_type, file_obj, memory_list)
    client.files.delete(name=uploaded_file.name)

if __name__ == "__main__":
    process_files()