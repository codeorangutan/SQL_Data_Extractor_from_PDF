def create_sat_speed_accuracy_chart(patient_id, db_path='cognitive_analysis.db'):
    """
    Creates a personalized Shifting Attention Test (SAT) speed-accuracy tradeoff chart
    showing the population trend line and the patient's position.
    
    Args:
        patient_id: The ID of the patient
        db_path: Path to the database file
        
    Returns:
        BytesIO: A BytesIO object containing the plot image data
    """
    try:
        # Define cache directory and file
        cache_dir = os.path.join('data', 'analysis_output', 'cached_data')
        os.makedirs(cache_dir, exist_ok=True)
        population_cache_file = os.path.join(cache_dir, 'sat_rt_errors_population_data.csv')
        regression_cache_file = os.path.join(cache_dir, 'sat_rt_errors_regression.json')
        
        # Try to load population data from cache
        population_df = None
        regression_params = None
        
        # Load population data if it exists
        if os.path.exists(population_cache_file):
            print(f"Loading cached SAT population data from {population_cache_file}")
            try:
                population_df = pd.read_csv(population_cache_file)
                # === ADDED CHECK: Verify if current patient is in the loaded cache ===
                if population_df is not None and not population_df.empty:
                    if str(patient_id) not in population_df['patient_id'].astype(str).values:
                        print(f"Patient {patient_id} not found in cached data. Discarding cache and querying DB.")
                        population_df = None # Force fallback to DB query
                    else:
                        print(f"Patient {patient_id} found in cached data.")
                # =======================================================================
            except Exception as e:
                print(f"Error loading cached population data: {e}")
                population_df = None # Fallback to DB query on error
        
        # If not in cache OR patient wasn't found in cache, query from database
        if population_df is None:
            print("SAT population data not cached or incomplete for patient, querying database...")
            try:
                # Connect to the database
                conn = sqlite3.connect(db_path)
                
                # First, verify what data exists for this patient
                debug_query = """
                SELECT patient_id, subtest_name, metric, score, standard_score, percentile
                FROM subtest_results 
                WHERE patient_id = ? 
                AND subtest_name LIKE '%Shifting Attention Test%'
                """
                debug_df = pd.read_sql_query(debug_query, conn, params=(patient_id,))
                if not debug_df.empty:
                    print(f"Found SAT data for patient {patient_id}:")
                    print(debug_df)
                else:
                    print(f"No SAT data found for patient {patient_id} in debug query")
                
                # Get population data for the regression line - use more flexible matching
                query = """
                SELECT sr1.patient_id, sr1.standard_score as rt_score, sr2.standard_score as err_score
                FROM subtest_results sr1
                JOIN subtest_results sr2 ON sr1.patient_id = sr2.patient_id
                WHERE sr1.subtest_name LIKE '%Shifting Attention Test%'
                AND sr1.metric LIKE '%Correct Reaction Time%' 
                AND sr2.subtest_name LIKE '%Shifting Attention Test%'
                AND sr2.metric LIKE '%Errors%' 
                """
                population_df = pd.read_sql_query(query, conn)
                print(f"Found {len(population_df)} patients with SAT data for population analysis")
                
                # Check if our patient is in the results
                if str(patient_id) in population_df['patient_id'].astype(str).values:
                    print(f"Patient {patient_id} is in the population dataset")
                else:
                    print(f"Patient {patient_id} NOT found in population dataset. Available IDs: {population_df['patient_id'].unique()[:5]}...")
                
                conn.close()
                
                # Save population data to cache
                if not population_df.empty:
                    print(f"Saving population data to cache: {population_cache_file}")
                    try:
                        population_df.to_csv(population_cache_file, index=False)
                    except Exception as e:
                        print(f"Error saving population data to cache: {e}")
            except Exception as e:
                print(f"Error querying database for SAT data: {e}")
                return None
            
        if population_df is None or population_df.empty:
            print(f"No SAT data found in the database or cache")
            return None
        
        # Get the specific patient's data
        try:
            # Convert patient_id to string for matching
            str_patient_id = str(patient_id)
            # Make matching more robust by comparing string versions
            patient_data = population_df[population_df['patient_id'].astype(str) == str_patient_id]
            
            if patient_data.empty:
                print(f"No SAT data found for patient ID {patient_id} in the processed dataset")
                print(f"Available patient IDs: {population_df['patient_id'].unique()[:5]}...")
                return None
            else:
                print(f"Found SAT data for patient {patient_id}: RT={patient_data['rt_score'].values[0]}, Errors={patient_data['err_score'].values[0]}")
        except Exception as e:
            print(f"Error filtering data for patient {patient_id}: {e}")
            return None
        
        # Convert to numeric and drop NaNs
        try:
            population_df['rt_score'] = pd.to_numeric(population_df['rt_score'], errors='coerce')
            population_df['err_score'] = pd.to_numeric(population_df['err_score'], errors='coerce')
            population_df = population_df.dropna(subset=['rt_score', 'err_score'])
            
            if len(population_df) < 10:
                print(f"Insufficient SAT data points after cleaning: {len(population_df)}")
                return None
        except Exception as e:
            print(f"Error converting data types: {e}")
            return None
        
        # Try to load regression parameters from cache
        if os.path.exists(regression_cache_file):
            print(f"Loading cached regression parameters from {regression_cache_file}")
            try:
                import json
                with open(regression_cache_file, 'r') as f:
                    regression_params = json.load(f)
                slope = regression_params['slope']
                intercept = regression_params['intercept']
                r_value = regression_params['r_value']
                p_value = regression_params['p_value']
                std_err = regression_params['std_err']
                corr = regression_params['corr']
                p = regression_params['p']
            except Exception as e:
                print(f"Error loading regression parameters: {e}")
                regression_params = None
        
        # Calculate regression if not in cache
        if regression_params is None:
            try:
                # Calculate and plot the regression line for the population
                slope, intercept, r_value, p_value, std_err = stats.linregress(
                    population_df['rt_score'], population_df['err_score'])
                
                # Calculate Spearman correlation
                corr, p = stats.spearmanr(population_df['rt_score'], population_df['err_score'])
                
                # Save regression parameters to cache
                regression_params = {
                    'slope': float(slope),
                    'intercept': float(intercept),
                    'r_value': float(r_value),
                    'p_value': float(p_value),
                    'std_err': float(std_err),
                    'corr': float(corr),
                    'p': float(p)
                }
                
                try:
                    import json
                    with open(regression_cache_file, 'w') as f:
                        json.dump(regression_params, f)
                    print(f"Saved regression parameters to cache: {regression_cache_file}")
                except Exception as e:
                    print(f"Error saving regression parameters: {e}")
            except Exception as e:
                print(f"Error calculating regression: {e}")
                return None
        
        try:
            # Generate x values across the range for the line
            x_min, x_max = population_df['rt_score'].min(), population_df['rt_score'].max()
            x_line = np.linspace(x_min, x_max, 100)
            y_line = slope * x_line + intercept
            
            # Plot regression line
            plt.plot(x_line, y_line, color='red', linewidth=2)
            
            # Add patient's point
            patient_rt = patient_data['rt_score'].values[0]
            patient_err = patient_data['err_score'].values[0]
            plt.scatter(patient_rt, patient_err, color='blue', s=100, marker='o', 
                        label=f'Patient {patient_id}')
            
            # Highlight patient position with a vertical and horizontal line to axes
            plt.axvline(x=patient_rt, color='blue', linestyle='--', alpha=0.5)
            plt.axhline(y=patient_err, color='blue', linestyle='--', alpha=0.5)
            
            # Clean labels and add interpretation notes
            rt_interp = "(Lower=Faster)"
            err_interp = "(Higher=More Errors)"
            
            plt.title(f"Speed vs. Accuracy: Shifting Attention Test (SAT)\nPopulation Spearman R={corr:.2f}, p={p:.6f}, N={len(population_df)}")
            plt.xlabel(f"Reaction Time\n{rt_interp}")
            plt.ylabel(f"Errors\n{err_interp}")
            plt.grid(True, alpha=0.3)
            plt.legend()
            
            # Add quadrant labels to help interpretation
            plt.annotate("Fast & Accurate", xy=(x_min, population_df['err_score'].min()), 
                        xytext=(10, 10), textcoords='offset points', color='green')
            plt.annotate("Slow & Inaccurate", xy=(x_max, population_df['err_score'].max()), 
                        xytext=(-10, -10), textcoords='offset points', color='red', ha='right')
            
            plt.tight_layout()
            
            # Instead of saving to file, save to BytesIO
            img_data = BytesIO()
            plt.savefig(img_data, format='png', bbox_inches='tight')
            img_data.seek(0)
            plt.close()
            
            return img_data
        except Exception as e:
            print(f"Error creating plot: {e}")
            plt.close()
            return None
    
    except Exception as e:
        print(f"Error creating SAT speed-accuracy chart: {e}")
        return None


def create_domain_explanation_page(styles):
    """Generates the ReportLab flowables for the domain score explanation page using a table."""
    explanation_elements = []
    explanation_elements.append(create_section_title("Cognitive Domain Score Calculation"))
    explanation_elements.append(Spacer(1, 12))
    
    text = f"""
    The scores presented on the Cognitive Profile radar chart represent performance across various cognitive domains. 
    These scores are derived from specific subtest metrics according to the CNS Vital Signs calculation methods, and then typically converted to percentiles for comparison against a normative group. 
    Below is a summary of how each domain score is calculated based on the raw test metrics:
    """
    explanation_elements.append(Paragraph(text, styles['Normal']))
    explanation_elements.append(Spacer(1, 18))

    # Data for the table [Domain, Formula]
    # Formulas condensed for single-line display
    table_data = [
        # Header Row
        [Paragraph("<b>Cognitive Domain</b>", styles['Normal']), Paragraph("<b>Calculation Formula (based on Raw Metrics)</b>", styles['Normal'])],
        # Domain Rows - Added ALL domains from user provided list
        ["Neurocognition Index (NCI)", "Avg: (Comp Mem + Psycho Speed + RT + Comp Attn + Cog Flex) / 5"],
        ["Composite Memory", "Sum: VBM & VIM Hits & Passes (Immediate & Delay)"], # Further condensed
        ["Verbal Memory", "Sum: VBM Hits Imm + VBM Pass Imm + VBM Hits Delay + VBM Pass Delay"],
        ["Visual Memory", "Sum: VIM Hits Imm + VIM Pass Imm + VIM Hits Delay + VIM Pass Delay"],
        ["Psychomotor Speed", "Sum: FTT Right Avg + FTT Left Avg + SDC Correct"],
        ["Reaction Time", "Mean: (ST Complex RT Correct + Stroop RT Correct) / 2"],
        ["Complex Attention", "Sum Errors: Stroop Comm Err + SAT Err + CPT Comm Err + CPT Omis Err"],
        ["Cognitive Flexibility", "SAT Correct - SAT Errors - Stroop Commission Errors"],
        ["Processing Speed", "SDC Correct Responses - SDC Errors"],
        ["Executive Function", "SAT Correct Responses - SAT Errors"],
        ["Simple Attention", "CPT Correct Responses - CPT Commission Errors"],
        ["Motor Speed", "FTT Right Taps Average + FTT Left Taps Average"],
        ["Working Memory", "4PCPT Part 4 Correct - Part 4 Incorrect"],
        ["Sustained Attention", "Sum(4PCPT P2-P4 Correct) - Sum(4PCPT P2-P4 Incorrect)"], # Condensed
        ["Social Acuity", "POET Correct Responses - POET Commission Errors"],
        ["Reasoning (Non-verbal)", "NVRT Correct Responses - NVRT Commission Errors"],
    ]

    # Create the table
    # Adjust colWidths as needed, None allows auto-sizing
    col_widths = [130, None] 
    explanation_table = Table(table_data, colWidths=col_widths)

    # Style the table
    style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),      # Header background
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke), # Header text color
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),              # Left align all
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),            # Middle align vertically
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),  # Header font bold
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),           # Header padding
        ('TOPPADDING', (0, 0), (-1, -1), 5),              # Padding for all cells
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),          # Padding for all cells
        ('LEFTPADDING', (0, 0), (-1, -1), 8),             # Padding for all cells
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),            # Padding for all cells
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),     # Grid lines
        # Zebra striping (alternating background colors for rows)
        # Apply to rows starting from index 1 (skip header)
    ])
    # Apply zebra striping
    for i in range(1, len(table_data)):
        if i % 2 == 0: # Even rows (adjust index if header is included differently)
            style.add('BACKGROUND', (0, i), (-1, i), colors.whitesmoke)
        else: # Odd rows
            style.add('BACKGROUND', (0, i), (-1, i), colors.lightblue)
            
    explanation_table.setStyle(style)

    explanation_elements.append(explanation_table)
    explanation_elements.append(Spacer(1, 12))
    
    explanation_elements.append(Paragraph("Note: Percentiles compare an individual's score to a normative group. A percentile of 50 represents average performance. Scores marked (INVALID) indicate the source test failed validity checks.", styles['Italic']))

    return explanation_elements