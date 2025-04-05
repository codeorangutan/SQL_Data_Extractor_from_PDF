import sqlite3
import re
import os
import fitz
import csv # PyMuPDF

DB_PATH = "cognitive_analysis.db"
PDF_PATH = "34766-20231015201357.pdf"

# --- DB Setup ---
def create_db(reset=False):
    if reset and os.path.exists(DB_PATH):
        try:
            os.remove(DB_PATH)
        except PermissionError:
            print(f"Warning: Could not remove {DB_PATH}. It may be in use.")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # Create tables
    cur.execute("""
    CREATE TABLE IF NOT EXISTS patients (
        patient_id INTEGER PRIMARY KEY,
        test_date TEXT,
        age INTEGER,
        language TEXT
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS cognitive_scores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER,
        domain TEXT,
        patient_score TEXT,
        standard_score INTEGER,
        percentile INTEGER,
        validity_index TEXT,
        FOREIGN KEY(patient_id) REFERENCES patients(patient_id)
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS subtest_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER,
        subtest_name TEXT,
        metric TEXT,
        score REAL,
        standard_score INTEGER,
        percentile INTEGER,
        validity_flag TEXT,
        FOREIGN KEY(patient_id) REFERENCES patients(patient_id)
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS asrs_responses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER,
        question_number INTEGER,
        part TEXT,
        response TEXT,
        FOREIGN KEY(patient_id) REFERENCES patients(patient_id)
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS dass21_scores(
        patient_id INTEGER,
        question_number INTEGER,
        response_score INTEGER,
        response_text TEXT,
        depression INTEGER,
        anxiety INTEGER,
        stress INTEGER,
        FOREIGN KEY(patient_id) REFERENCES patients(patient_id)
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS dass21_responses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER,
        question_number INTEGER,
        response_score INTEGER,
        response_text TEXT,
        FOREIGN KEY(patient_id) REFERENCES patients(patient_id)
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS epworth_scores (
        patient_id INTEGER,
        question_number INTEGER,
        situation TEXT,
        score INTEGER,
        description TEXT,
        FOREIGN KEY(patient_id) REFERENCES patients(patient_id)
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS epworth_total (
        patient_id INTEGER,
        total_score INTEGER,
        interpretation TEXT,
        FOREIGN KEY(patient_id) REFERENCES patients(patient_id),
        PRIMARY KEY(patient_id)
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS test_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER,
        section TEXT,
        status TEXT,
        FOREIGN KEY(patient_id) REFERENCES patients(patient_id)
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS npq_scores (
        patient_id INTEGER,
        domain TEXT,
        score INTEGER,
        severity TEXT,
        description TEXT,
        FOREIGN KEY(patient_id) REFERENCES patients(patient_id)
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS npq_questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER,
        domain TEXT,
        question_number INTEGER,
        question_text TEXT,
        score INTEGER,
        severity TEXT,
        FOREIGN KEY(patient_id) REFERENCES patients(patient_id)
    )""")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS asrs_dsm_diagnosis (
            patient_id TEXT PRIMARY KEY,
            inattentive_criteria_met INTEGER,
            hyperactive_criteria_met INTEGER,
            diagnosis TEXT,
            FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
        )
    """)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS dsm_criteria_met (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id TEXT,
            dsm_criterion TEXT,
            dsm_category TEXT,
            is_met INTEGER,
            FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
        )
    """)

    conn.commit()
    conn.close()

# --- Data Extraction ---
def extract_text_blocks(pdf_path):
    import fitz  # ensure imported

    doc = fitz.open(pdf_path)
    all_lines = []

    for page in doc:
        blocks = page.get_text("blocks")  # (x0, y0, x1, y1, text, block_no, block_type)
        blocks = sorted(blocks, key=lambda b: (b[1], b[0]))  # sort top-down, then left-right
        for b in blocks:
            lines = b[4].splitlines()
            all_lines.extend(line.strip() for line in lines if line.strip())
            in_npq = False
            for line in lines:
                if "NeuroPsych Questionnaire" in line:
                    in_npq = True
                if in_npq:
                    print("[NPQ RAW]", line)

    return all_lines

def extract_npq_text(pdf_path):
    import pdfplumber
    lines = []
    npq_page_found = False
    
    with pdfplumber.open(pdf_path) as pdf:
        # First identify which page contains the NPQ section
        for i in range(len(pdf.pages)):
            text = pdf.pages[i].extract_text()
            if text and ("NeuroPsych Questionnaire" in text or "Domain Score Severity" in text):
                npq_page_found = True
                print(f"[DEBUG] Found NPQ on page {i+1}")
                # Once we find the NPQ section, extract from this page and a few pages after
                for j in range(i, min(i+5, len(pdf.pages))):
                    page_text = pdf.pages[j].extract_text()
                    if page_text:
                        # Check if we've reached the end of NPQ section
                        if j > i and "NeuroPsych Questionnaire" not in page_text and "Domain Score" not in page_text:
                            # Additional check to see if this page likely contains NPQ content
                            if not any(domain in page_text for domain in ["Attention", "Anxiety", "Depression", "Memory"]):
                                break
                        
                        print(f"[DEBUG] Extracting NPQ from page {j+1}")
                        page_lines = page_text.splitlines()
                        clean_lines = []
                        for line in page_lines:
                            line = line.strip()
                            if line:
                                clean_lines.append(line)
                                
                        lines.extend(clean_lines)
                break
                
    if not npq_page_found:
        # Fallback to scanning a broader range of pages
        with pdfplumber.open(pdf_path) as pdf:
            for i in range(5, min(13, len(pdf.pages))):  # Pages 6-13 (0-indexed)
                text = pdf.pages[i].extract_text()
                if text:
                    print(f"[DEBUG] Fallback: Checking page {i+1} for NPQ content")
                    if "NeuroPsych Questionnaire" in text or "Domain Score Severity" in text:
                        print(f"[DEBUG] Found NPQ content on page {i+1} during fallback")
                    page_lines = text.splitlines()
                    lines.extend(l.strip() for l in page_lines if l.strip())
    
    # Debug the first few lines to help diagnose issues
    print("[DEBUG] First few NPQ extracted lines:")
    for idx, line in enumerate(lines[:20]):
        print(f"  {idx}: {line}")
        
    return lines

def extract_npq_table(pdf_path):
    """Extract NPQ data using table extraction approach"""
    import pdfplumber
    
    with pdfplumber.open(pdf_path) as pdf:
        # Search for the NPQ section in the PDF
        npq_pages = []
        for i in range(len(pdf.pages)):
            text = pdf.pages[i].extract_text()
            if text and ("NeuroPsych Questionnaire" in text or "Domain Score Severity" in text):
                npq_pages.append(i)
                print(f"[DEBUG] Found NPQ on page {i+1}")
        
        if not npq_pages:
            print("[WARN] No NPQ pages found")
            return [], []
        
        # Extract tables from NPQ pages
        all_tables = []
        for page_idx in npq_pages:
            page = pdf.pages[page_idx]
            tables = page.extract_tables()
            if tables:
                print(f"[DEBUG] Found {len(tables)} tables on page {page_idx+1}")
                all_tables.extend(tables)
            else:
                print(f"[DEBUG] No tables found on page {page_idx+1}")
        
        # Process tables to extract domain data
        domain_data = []
        question_data = []
        
        for table_idx, table in enumerate(all_tables):
            print(f"[DEBUG] Processing table {table_idx+1} with {len(table)} rows")
            
            # Check if this is a domain table
            is_domain_table = False
            for row in table:
                if row and len(row) >= 3:
                    # Check if any cell contains "Domain", "Score", "Severity"
                    header_cells = [cell for cell in row if cell and isinstance(cell, str)]
                    if any("Domain" in cell for cell in header_cells) and any("Score" in cell for cell in header_cells):
                        is_domain_table = True
                        print(f"[DEBUG] Table {table_idx+1} is a domain table")
                        break
            
            if is_domain_table:
                # Process domain table
                for row in table:
                    if row and len(row) >= 3 and all(cell is not None for cell in row[:3]):
                        domain = row[0]
                        # Skip header row
                        if domain == "Domain" or "Domain" in domain:
                            continue
                        
                        try:
                            score = int(row[1]) if row[1] and row[1].isdigit() else None
                            severity = row[2] if row[2] else ""
                            
                            if domain and score is not None:
                                print(f"[DEBUG] Found domain: {domain}, score: {score}, severity: {severity}")
                                domain_data.append((domain, score, severity))
                        except (ValueError, TypeError) as e:
                            print(f"[WARN] Error parsing domain row: {row} - {e}")
            else:
                # This might be a question table
                for row in table:
                    if row and len(row) >= 4:
                        try:
                            # Check if first cell is a number (question number)
                            if row[0] and row[0].isdigit():
                                question_num = int(row[0])
                                question_text = row[1] if row[1] else ""
                                score = int(row[2]) if row[2] and row[2].isdigit() else None
                                severity = row[3] if row[3] else ""
                                
                                if question_text and score is not None:
                                    print(f"[DEBUG] Found question: {question_num}, {question_text}, score: {score}")
                                    question_data.append((question_num, question_text, score, severity))
                        except (ValueError, TypeError) as e:
                            print(f"[WARN] Error parsing question row: {row} - {e}")
        
        # If no tables were found or processed, try to extract using bounding boxes
        if not domain_data:
            print("[DEBUG] No domain data found in tables, trying bounding box extraction")
            domain_data, question_data = extract_npq_with_bounding_boxes(pdf, npq_pages)
    
    return domain_data, question_data

def extract_npq_with_bounding_boxes(pdf, npq_pages):
    """Extract NPQ data using bounding boxes for when table extraction fails"""
    domain_data = []
    question_data = []
    
    # Known domains for validation
    domains = [
        "Attention", "Impulsive", "Learning", "Memory", "Fatigue", "Sleep", 
        "Anxiety", "Panic", "Agoraphobia", "Obsessions & Compulsions", "Social Anxiety", 
        "PTSD", "Depression", "Bipolar", "Mood Stability", "Mania", "Aggression", 
        "Autism", "Asperger's", "Psychotic", "Somatic", "Suicide", "Pain", 
        "Substance Abuse", "MCI", "Concussion", "ADHD", "Average Symptom Score", "Anxiety/Depression"
    ]
    
    # Severity levels for validation
    severity_levels = ["Severe", "Moderate", "Mild", "Not a problem"]
    
    # Track the current domain for question parsing
    current_domain = None
    in_question_section = False
    
    for page_idx in npq_pages:
        page = pdf.pages[page_idx]
        print(f"[DEBUG] Processing page {page_idx+1} with bounding box method")
        
        # Extract all words with their positions
        words = page.extract_words(x_tolerance=3, y_tolerance=3)
        
        # Group words by their y-position (same line)
        lines = {}
        for word in words:
            y = round(word["top"])
            if y not in lines:
                lines[y] = []
            lines[y].append(word)
        
        # Sort lines by y-position
        sorted_y = sorted(lines.keys())
        
        # Process each line
        for i, y in enumerate(sorted_y):
            line_words = sorted(lines[y], key=lambda w: w["x0"])
            line_text = " ".join(word["text"] for word in line_words)
            
            # Check for question section headers (e.g., "Attention Questions")
            question_section_match = re.search(r'^(\w+)\s+Questions$', line_text)
            if question_section_match:
                current_domain = question_section_match.group(1)
                print(f"[DEBUG] Found question section for domain: {current_domain}")
                continue
            
            # Check if this is a question line (starts with a number)
            if in_question_section and current_domain:
                question_match = re.match(r'^(\d+)\s+(.+)$', line_text)
                
                if question_match:
                    question_num = int(question_match.group(1))
                    question_text = question_match.group(2).strip()
                    
                    # Get the next line (potential answer)
                    if i + 1 < len(lines):
                        answer_y = sorted_y[i + 1]
                        answer_line = " ".join(word["text"] for word in sorted(lines[answer_y], key=lambda w: w["x0"]))
                        
                        # Try to match answer pattern (e.g., "3 - Moderate")
                        answer_match = re.match(r'^(\d+)\s*-\s*(.+)$', answer_line)
                        
                        if answer_match:
                            score = int(answer_match.group(1))
                            severity = answer_match.group(2).strip()
                            
                            print(f"[DEBUG] Found question: {question_num}, '{question_text[:40]}...' -> {score} - {severity}")
                            question_data.append((question_num, question_text, score, severity, current_domain))
            
            # Check if this line contains a domain
            domain_match = None
            for domain in domains:
                if domain in line_text:
                    domain_match = domain
                    break
            
            if domain_match and i + 2 < len(sorted_y):
                # Get the next two lines (potential score and severity)
                score_y = sorted_y[i + 1]
                severity_y = sorted_y[i + 2]
                
                score_line = " ".join(word["text"] for word in sorted(lines[score_y], key=lambda w: w["x0"]))
                severity_line = " ".join(word["text"] for word in sorted(lines[severity_y], key=lambda w: w["x0"]))
                
                # Try to extract score (should be just a number)
                score_match = re.search(r'^\s*(\d+)\s*$', score_line)
                
                # Check if severity is one of the expected values
                severity_match = None
                for level in severity_levels:
                    if level in severity_line:
                        severity_match = level
                        break
                
                if score_match and severity_match:
                    score = int(score_match.group(1))
                    severity = severity_match
                    
                    print(f"[DEBUG] Found domain via bounding boxes: {domain_match}, score: {score}, severity: {severity}")
                    domain_data.append((domain_match, score, severity))
    
    # Print summary of what we found
    print(f"[DEBUG] Found {len(domain_data)} domains via bounding boxes:")
    for domain, score, severity in domain_data:
        print(f"  - {domain}: {score}, {severity}")
    
    print(f"[DEBUG] Found {len(question_data)} questions via bounding boxes")
    
    return domain_data, question_data