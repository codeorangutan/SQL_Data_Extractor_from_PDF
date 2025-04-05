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