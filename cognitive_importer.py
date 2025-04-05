import sqlite3
import re
import os
import fitz
import csv # PyMuPDF
import pdfplumber
import traceback

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

def extract_npq_questions_pymupdf(pdf_path, patient_id):
    """Extract NPQ questions using PyMuPDF for better text extraction"""
    doc = fitz.open(pdf_path)
    questions = []
    current_domain = None
    
    # Define severity mapping
    severity_map = {
        0: "Not a problem",
        1: "Mild",
        2: "Moderate",
        3: "Severe"
    }
    
    # Known domains for validation
    domains = [
        "Attention", "Impulsive", "Learning", "Memory", "Fatigue", "Sleep", 
        "Anxiety", "Panic", "Agoraphobia", "Obsessions & Compulsions", "Social Anxiety", 
        "PTSD", "Depression", "Bipolar", "Mood Stability", "Mania", "Aggression", 
        "Autism", "Asperger's", "Psychotic", "Somatic", "Suicide", "Pain", 
        "Substance Abuse", "MCI", "Concussion", "ADHD"
    ]
    
    # Find NPQ pages
    npq_pages = []
    for page_idx in range(len(doc)):
        page = doc[page_idx]
        text = page.get_text()
        if "NeuroPsych Questionnaire" in text or "Domain Score Severity" in text:
            npq_pages.append(page_idx)
            print(f"[DEBUG] Found NPQ on page {page_idx+1}")
    
    if not npq_pages:
        print("[WARN] No NPQ pages found")
        return []
    
    # Process NPQ pages
    for page_idx in npq_pages:
        page = doc[page_idx]
        blocks = page.get_text("blocks")
        blocks = sorted(blocks, key=lambda b: (b[1], b[0]))  # sort by y, then x
        
        for block in blocks:
            text = block[4]
            lines = text.splitlines()
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Check for domain headers
                for domain in domains:
                    if domain == line or f"{domain}:" == line:
                        current_domain = domain
                        print(f"[DEBUG] Found domain header: {current_domain}")
                        break
                
                # Check for questions (number followed by text)
                question_match = re.match(r'^(\d+)\.\s+(.+)$', line)
                if question_match:
                    question_num = int(question_match.group(1))
                    question_text = question_match.group(2).strip()
                    
                    # Look for score in the next line or at the end of this line
                    score = None
                    severity = None
                    
                    # Check if score is at the end of the question text
                    score_match = re.search(r'(\d+)\s*$', question_text)
                    if score_match:
                        potential_score = int(score_match.group(1))
                        if 0 <= potential_score <= 3:  # Valid NPQ score range
                            score = potential_score
                            severity = severity_map.get(score, "Unknown")
                            # Remove the score from the question text
                            question_text = question_text[:score_match.start()].strip()
                    
                    # If we found a valid question with score
                    if question_text and score is not None and current_domain:
                        print(f"[DEBUG] Found question: {question_num}, '{question_text[:40]}...', domain: {current_domain}, score: {score}")
                        questions.append((patient_id, current_domain, question_num, question_text, score, severity))
    
    print(f"[DEBUG] Total NPQ questions extracted: {len(questions)}")
    return questions

def parse_npq_scores(lines):
    """Parse NPQ domain scores from extracted text lines"""
    domain_scores = []
    domain_pattern = re.compile(r'^([A-Za-z\'& ]+)\s+(\d+)\s+(Severe|Moderate|Mild|Not a problem)$')
    
    # Also try to match lines with domain and score on separate lines
    current_domain = None
    current_score = None
    
    for line in lines:
        # Try direct pattern match first
        match = domain_pattern.match(line)
        if match:
            domain = match.group(1).strip()
            score = int(match.group(2))
            severity = match.group(3)
            domain_scores.append((domain, score, severity))
            print(f"[DEBUG] Direct match - Domain: {domain}, Score: {score}, Severity: {severity}")
            continue
        
        # If no direct match, try to identify domain names, scores, and severities separately
        if any(domain in line for domain in [
            "Attention", "Impulsive", "Learning", "Memory", "Fatigue", "Sleep", 
            "Anxiety", "Panic", "Agoraphobia", "Obsessions & Compulsions", "Social Anxiety", 
            "PTSD", "Depression", "Bipolar", "Mood Stability", "Mania", "Aggression", 
            "Autism", "Asperger's", "Psychotic", "Somatic", "Suicide", "Pain", 
            "Substance Abuse", "MCI", "Concussion", "ADHD"
        ]):
            # This line likely contains a domain name
            current_domain = line.strip()
            current_score = None
            print(f"[DEBUG] Found potential domain: {current_domain}")
        
        # Check if this line contains just a number (potential score)
        elif line.strip().isdigit() and current_domain and not current_score:
            current_score = int(line.strip())
            print(f"[DEBUG] Found potential score for {current_domain}: {current_score}")
        
        # Check if this line contains a severity level
        elif current_domain and current_score and any(severity in line for severity in ["Severe", "Moderate", "Mild", "Not a problem"]):
            for severity in ["Severe", "Moderate", "Mild", "Not a problem"]:
                if severity in line:
                    domain_scores.append((current_domain, current_score, severity))
                    print(f"[DEBUG] Assembled match - Domain: {current_domain}, Score: {current_score}, Severity: {severity}")
                    current_domain = None
                    current_score = None
                    break
    
    return domain_scores

def insert_npq_scores(domain_scores, patient_id, conn=None):
    """Insert NPQ domain scores into the database"""
    close_conn = False
    if conn is None:
        conn = sqlite3.connect(DB_PATH)
        close_conn = True
    
    cur = conn.cursor()
    
    # First, delete any existing records for this patient
    cur.execute("DELETE FROM npq_scores WHERE patient_id = ?", (patient_id,))
    
    # Insert new records
    for domain, score, severity in domain_scores:
        # Add a description based on severity
        description = ""
        if severity == "Severe":
            description = "Clinically significant, requires attention"
        elif severity == "Moderate":
            description = "Potentially significant, monitor closely"
        elif severity == "Mild":
            description = "Mild concern, may benefit from monitoring"
        else:
            description = "Not clinically significant"
        
        cur.execute("""
            INSERT INTO npq_scores (patient_id, domain, score, severity, description)
            VALUES (?, ?, ?, ?, ?)
        """, (patient_id, domain, score, severity, description))
    
    conn.commit()
    
    if close_conn:
        conn.close()
    
    print(f"[INFO] Inserted {len(domain_scores)} NPQ domain scores for patient {patient_id}")

def extract_and_insert_npq_scores(pdf_path, patient_id, conn=None):
    """Extract and insert NPQ domain scores"""
    try:
        # Extract NPQ text
        npq_lines = extract_npq_text(pdf_path)
        
        # Try table-based extraction first
        domain_data, _ = extract_npq_table(pdf_path)
        
        # If table extraction didn't work, try parsing from text
        if not domain_data:
            domain_data = parse_npq_scores(npq_lines)
        
        # Insert into database
        if domain_data:
            insert_npq_scores(domain_data, patient_id, conn)
            return True
        else:
            print("[WARN] No NPQ domain scores found to insert")
            return False
    
    except Exception as e:
        print(f"Error extracting/inserting NPQ scores: {e}")
        traceback.print_exc()
        return False

def insert_npq_questions(questions, conn=None):
    """Insert NPQ questions into the database"""
    close_conn = False
    if conn is None:
        conn = sqlite3.connect(DB_PATH)
        close_conn = True
    
    cur = conn.cursor()
    
    # If we have questions, first delete any existing records for this patient
    if questions:
        patient_id = questions[0][0]  # First element of first tuple
        cur.execute("DELETE FROM npq_questions WHERE patient_id = ?", (patient_id,))
        
        # Use executemany for better performance
        cur.executemany("""
            INSERT INTO npq_questions (patient_id, domain, question_number, question_text, score, severity)
            VALUES (?, ?, ?, ?, ?, ?)
        """, questions)
        
        conn.commit()
        print(f"[INFO] Inserted {len(questions)} NPQ questions for patient {patient_id}")
    else:
        print("[WARN] No NPQ questions to insert")
    
    if close_conn:
        conn.close()
    
    return len(questions) > 0

def extract_and_insert_npq_questions(pdf_path, patient_id, conn=None):
    """Extract and insert NPQ questions"""
    try:
        # Extract questions using PyMuPDF for better text extraction
        questions = extract_npq_questions_pymupdf(pdf_path, patient_id)
        
        # Insert into database
        if questions:
            success = insert_npq_questions(questions, conn)
            return success
        else:
            print("[WARN] No NPQ questions found to insert")
            return False
    
    except Exception as e:
        print(f"Error extracting/inserting NPQ questions: {e}")
        traceback.print_exc()
        return False