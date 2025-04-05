import sqlite3
import logging
import pandas as pd
from collections import defaultdict

# Set up logging
logging.basicConfig(
    filename='data_access.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filemode='a'  # Append to existing log file
)

def debug_log(message):
    """Log debug message to file and print to console"""
    logging.debug(message)
    print(message)

def patient_exists_in_db(patient_id, db_path="cognitive_analysis.db"):
    """Check if the patient has valid data in the database."""
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        
        # Check if patient exists in the patients table
        patient = cur.execute("SELECT * FROM patients WHERE patient_id = ?", (patient_id,)).fetchone()
        
        # Check if cognitive scores exist for the patient
        scores = cur.execute("SELECT COUNT(*) FROM cognitive_scores WHERE patient_id = ?", (patient_id,)).fetchone()
        
        # Check if subtest results exist for the patient
        subtests = cur.execute("SELECT COUNT(*) FROM subtest_results WHERE patient_id = ?", (patient_id,)).fetchone()
        
        conn.close()
        
        # Return True if the patient exists and has at least some data
        return (patient is not None) and (scores[0] > 0 or subtests[0] > 0)
    
    except Exception as e:
        debug_log(f"[ERROR] Error checking if patient exists: {e}")
        return False

def check_data_completeness(patient_id, db_path="cognitive_analysis.db"):
    """
    Check if all required data components are available for the patient.
    Returns a dictionary with status of each component.
    """
    result = {
        "patient_info": False,
        "cognitive_scores": False,
        "subtests": False,
        "asrs": False,
        "dass": False,
        "epworth": False,
        "npq": False
    }
    
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        
        # Check patient info
        patient = cur.execute("SELECT * FROM patients WHERE patient_id = ?", (patient_id,)).fetchone()
        result["patient_info"] = patient is not None
        
        # Check cognitive scores
        scores = cur.execute("SELECT COUNT(*) FROM cognitive_scores WHERE patient_id = ?", (patient_id,)).fetchone()
        result["cognitive_scores"] = scores[0] > 0
        
        # Check subtests
        subtests = cur.execute("SELECT COUNT(*) FROM subtest_results WHERE patient_id = ?", (patient_id,)).fetchone()
        result["subtests"] = subtests[0] > 0
        
        # Check ASRS
        asrs = cur.execute("SELECT COUNT(*) FROM asrs_responses WHERE patient_id = ?", (patient_id,)).fetchone()
        result["asrs"] = asrs[0] > 0
        
        # Check DASS
        dass = cur.execute("SELECT COUNT(*) FROM dass21_scores WHERE patient_id = ?", (patient_id,)).fetchone()
        result["dass"] = dass[0] > 0
        
        # Check Epworth
        epworth = cur.execute("SELECT COUNT(*) FROM epworth_scores WHERE patient_id = ?", (patient_id,)).fetchone()
        result["epworth"] = epworth[0] > 0
        
        # Check NPQ
        npq = cur.execute("SELECT COUNT(*) FROM npq_scores WHERE patient_id = ?", (patient_id,)).fetchone()
        result["npq"] = npq[0] > 0
        
        conn.close()
        
    except Exception as e:
        debug_log(f"[ERROR] Error checking data completeness: {e}")
    
    return result

def get_patient_data(patient_id, db_path="cognitive_analysis.db"):
    """Get patient basic information"""
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        patient = cur.execute("SELECT * FROM patients WHERE patient_id = ?", (patient_id,)).fetchone()
        conn.close()
        return patient
    except Exception as e:
        debug_log(f"[ERROR] Error getting patient data: {e}")
        return None

def get_cognitive_scores(patient_id, db_path="cognitive_analysis.db"):
    """Get cognitive scores for a patient"""
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        scores = cur.execute("SELECT * FROM cognitive_scores WHERE patient_id = ?", (patient_id,)).fetchall()
        conn.close()
        return scores
    except Exception as e:
        debug_log(f"[ERROR] Error getting cognitive scores: {e}")
        return []

def get_subtest_results(patient_id, db_path="cognitive_analysis.db"):
    """Get subtest results for a patient"""
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        subtests = cur.execute("SELECT * FROM subtest_results WHERE patient_id = ?", (patient_id,)).fetchall()
        conn.close()
        return subtests
    except Exception as e:
        debug_log(f"[ERROR] Error getting subtest results: {e}")
        return []

def get_asrs_responses(patient_id, db_path="cognitive_analysis.db"):
    """Get ASRS responses for a patient"""
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        asrs = cur.execute("SELECT * FROM asrs_responses WHERE patient_id = ?", (patient_id,)).fetchall()
        conn.close()
        return asrs
    except Exception as e:
        debug_log(f"[ERROR] Error getting ASRS responses: {e}")
        return []

def get_dass_data(patient_id, db_path="cognitive_analysis.db"):
    """Get DASS scores and responses for a patient"""
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        summary = cur.execute("SELECT * FROM dass21_scores WHERE patient_id = ?", (patient_id,)).fetchall()
        items = cur.execute("SELECT * FROM dass21_responses WHERE patient_id = ?", (patient_id,)).fetchall()
        conn.close()
        return {"summary": summary, "items": items}
    except Exception as e:
        debug_log(f"[ERROR] Error getting DASS data: {e}")
        return {"summary": [], "items": []}

def get_epworth_scores(patient_id, db_path="cognitive_analysis.db"):
    """Get Epworth scores for a patient"""
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        epworth = cur.execute("SELECT * FROM epworth_scores WHERE patient_id = ?", (patient_id,)).fetchall()
        conn.close()
        return epworth
    except Exception as e:
        debug_log(f"[ERROR] Error getting Epworth scores: {e}")
        return []

def get_npq_data(patient_id, db_path="cognitive_analysis.db"):
    """Get NPQ scores and questions for a patient"""
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        scores = cur.execute("SELECT * FROM npq_scores WHERE patient_id = ?", (patient_id,)).fetchall()
        questions = cur.execute("SELECT * FROM npq_questions WHERE patient_id = ?", (patient_id,)).fetchall()
        conn.close()
        return {"scores": scores, "questions": questions}
    except Exception as e:
        debug_log(f"[ERROR] Error getting NPQ data: {e}")
        return {"scores": [], "questions": []}

def get_domain_scores_for_radar(patient_id, db_path="cognitive_analysis.db"):
    """
    Directly query the database for domain scores needed for the radar chart.
    Returns a dictionary of domain names to percentile scores.
    Also returns a list of invalid domain names.
    """
    domain_percentiles = {}
    invalid_domains = []
    
    try:
        # Connect to the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Query to get standard scores for each domain
        query = """
        SELECT 
            domain, 
            patient_score, 
            standard_score, 
            percentile,
            validity_index
        FROM cognitive_scores 
        WHERE patient_id = ?
        """
        
        cursor.execute(query, (patient_id,))
        domain_results = cursor.fetchall()
        
        debug_log(f"Domain results from database: {domain_results}")
        
        if not domain_results:
            debug_log(f"No cognitive domains found for patient {patient_id}")
            return {}, []
        
        # Process each domain
        for result in domain_results:
            domain_name, raw_score, standard_score, percentile, validity_index = result
            
            # Check if this is a known domain we want to include
            domain_mapping = {
                "Verbal Memory": "Verbal Memory",
                "Visual Memory": "Visual Memory", 
                "Psychomotor Speed": "Psychomotor Speed",
                "Reaction Time": "Reaction Time",
                "Complex Attention": "Complex Attention",
                "Cognitive Flexibility": "Cognitive Flexibility",
                "Processing Speed": "Processing Speed",
                "Executive Function": "Executive Function",
            }
            
            # Get the standardized domain name if it exists, otherwise use as-is
            std_domain_name = domain_mapping.get(domain_name, domain_name)
            
            # Add to percentiles dictionary
            try:
                if percentile is not None:
                    domain_percentiles[std_domain_name] = int(percentile)
                    debug_log(f"Added domain {std_domain_name} with percentile {percentile}")
                else:
                    debug_log(f"Percentile is None for domain {std_domain_name}")
            except (ValueError, TypeError) as e:
                debug_log(f"Error processing percentile for {std_domain_name}: {e}")
            
            # Check validity
            if validity_index and validity_index.lower() == 'no':
                invalid_domains.append(std_domain_name)
                debug_log(f"Domain {std_domain_name} marked as invalid")
        
        # Query subtests for supplementary information
        subtest_query = """
        SELECT 
            subtest_name, 
            metric,
            score, 
            standard_score,
            percentile,
            validity_flag
        FROM subtest_results 
        WHERE patient_id = ?
        """
        
        cursor.execute(subtest_query, (patient_id,))
        subtest_results = cursor.fetchall()
        
        # If we're missing domains, check if we can extract them from subtests
        if len(domain_percentiles) < 8:
            debug_log(f"Only have {len(domain_percentiles)} domains, checking subtests")
            # Process subtests
            for result in subtest_results:
                subtest_name, metric, raw_score, std_score, percentile, validity = result
                debug_log(f"Checking subtest: {subtest_name}, {metric}")
                
                # Check if this subtest maps to a domain
                # This would need to be expanded with your specific mappings
                # For now, just an example
                if "Memory" in subtest_name and "Verbal" in subtest_name and "Verbal Memory" not in domain_percentiles:
                    domain_percentiles["Verbal Memory"] = int(percentile) if percentile else 0
                    debug_log(f"Added Verbal Memory from subtest with percentile {percentile}")
        
        conn.close()
        
    except Exception as e:
        debug_log(f"Error querying domain scores: {e}")
    
    return domain_percentiles, invalid_domains

def fetch_all_patient_data(patient_id, db_path="cognitive_analysis.db"):
    """
    Fetch all data for a patient in one go.
    Returns a dictionary with all patient data.
    """
    try:
        # Get individual data components
        patient = get_patient_data(patient_id, db_path)
        cognitive_scores = get_cognitive_scores(patient_id, db_path)
        subtests = get_subtest_results(patient_id, db_path)
        asrs = get_asrs_responses(patient_id, db_path)
        dass_data = get_dass_data(patient_id, db_path)
        epworth = get_epworth_scores(patient_id, db_path)
        npq_data = get_npq_data(patient_id, db_path)
        
        # Debug output for cognitive scores
        debug_log("\n=== COGNITIVE SCORES FROM DATABASE ===")
        for i, score in enumerate(cognitive_scores):
            debug_log(f"  Score {i+1}: {score}")
        debug_log("=====================================\n")
        
        # Combine all data
        return {
            "patient": patient,
            "cognitive_scores": cognitive_scores,
            "subtests": subtests,
            "asrs": asrs,
            "dass_summary": dass_data["summary"],
            "dass_items": dass_data["items"],
            "epworth": epworth,
            "npq_scores": npq_data["scores"],
            "npq_questions": npq_data["questions"]
        }
    except Exception as e:
        debug_log(f"[ERROR] Error fetching all patient data: {e}")
        return {
            "patient": None,
            "cognitive_scores": [],
            "subtests": [],
            "asrs": [],
            "dass_summary": [],
            "dass_items": [],
            "epworth": [],
            "npq_scores": [],
            "npq_questions": []
        }