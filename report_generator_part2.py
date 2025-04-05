def create_fancy_report(data, output_path):
    """
    Create a fancy PDF report with radar chart and tables.
    
    Args:
        data: Dict containing patient data
        output_path: Path to save the PDF report
    """
    # Create a PDF document
    doc = SimpleDocTemplate(output_path, pagesize=A4)
    styles = getSampleStyleSheet()
    
    # Add custom styles
    styles.add(
        'Italic', 
        styles['Normal'].clone('Italic', fontName='Helvetica-Oblique')
    )
    
    elements = []
    
    # Add patient information
    if data["patient"]:
        patient_id = data["patient"][0]
        patient_name = data["patient"][1] if len(data["patient"]) > 1 else "Unknown"
        patient_dob = data["patient"][2] if len(data["patient"]) > 2 else "Unknown"
        patient_sex = data["patient"][3] if len(data["patient"]) > 3 else "Unknown"
        
        elements.append(Paragraph(f"<b>Patient ID:</b> {patient_id}", styles['Normal']))
        elements.append(Paragraph(f"<b>Name:</b> {patient_name}", styles['Normal']))
        elements.append(Paragraph(f"<b>Date of Birth:</b> {patient_dob}", styles['Normal']))
        elements.append(Paragraph(f"<b>Sex:</b> {patient_sex}", styles['Normal']))
        elements.append(Spacer(1, 12))
    
    # Add cognitive profile section
    elements.append(create_section_title("Cognitive Profile"))
    
    # Add radar chart if cognitive scores are available
    if data["cognitive_scores"]:
        # Create a dictionary of domain scores
        domain_scores = {}
        invalid_domains = []
        
        for score in data["cognitive_scores"]:
            domain = score[1]
            percentile = score[3]
            is_valid = score[4] if len(score) > 4 else 1  # Default to valid if column doesn't exist
            
            # Check if the score is valid
            valid_str = str(is_valid).strip().lower()
            if valid_str not in ['1', 'yes', 'valid', 'true']:
                invalid_domains.append(domain)
                
            # Store the percentile score
            try:
                domain_scores[domain] = int(percentile) if percentile is not None else 0
            except (ValueError, TypeError):
                print(f"[WARN] Invalid percentile value for {domain}: {percentile}")
                domain_scores[domain] = 0
        
        # Create the radar chart
        radar_chart = create_radar_chart(domain_scores, invalid_domains)
        
        # Add the radar chart to the document
        elements.append(Image(radar_chart, width=400, height=400))
        elements.append(Spacer(1, 12))
        
        # Create a table with cognitive domain scores
        elements.append(create_section_title("Cognitive Domain Scores"))
        
        # Define table headers
        score_data = [["Domain", "Standard Score", "Percentile", "Classification", "Valid"]]
        
        # Define table styles
        table_styles = [
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),  # Make header bold
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ]
        
        # Add rows for each cognitive domain
        for row_idx, score in enumerate(data["cognitive_scores"], 1):
            domain = score[1]
            std_score = score[2]
            percentile = score[3]
            is_valid = score[4] if len(score) > 4 else 1  # Default to valid if column doesn't exist
            
            # Determine classification based on percentile
            classification = ""
            if percentile is not None:
                try:
                    p = int(percentile)
                    if p > 75:
                        classification = "Above Average"
                    elif p >= 25:
                        classification = "Average"
                    elif p >= 9:
                        classification = "Low Average"
                    elif p >= 2:
                        classification = "Low"
                    else:
                        classification = "Very Low"
                except (ValueError, TypeError):
                    classification = "Unknown"
            
            # Add row to table
            valid_str = str(is_valid).strip().lower()
            valid_display = "Yes" if valid_str in ['1', 'yes', 'valid', 'true'] else "No"
            score_data.append([domain, std_score, percentile, classification, valid_display])
            
            # Color code row based on percentile if valid
            if valid_str in ['1', 'yes', 'valid', 'true']:
                bg_color = get_percentile_color(percentile)
                table_styles.append(('BACKGROUND', (0, row_idx), (-1, row_idx), bg_color))
            
            # Make NCI row bold
            table_styles.append(('FONTNAME', (0, row_idx), (-1, row_idx), 'Helvetica-Bold'))
            
        # Create the table
        score_table = Table(score_data, colWidths=[120, 100, 80, 100, 60])
        score_table.setStyle(TableStyle(table_styles))
        elements.append(score_table)
        elements.append(Spacer(1, 12))
    
    else:
        print("[WARN] No cognitive_scores found for patient")
        elements.append(Paragraph("Cognitive domain scores were not available.", styles['Normal']))
    
    # Add color legend for percentile ranges
    elements.append(create_section_title("Score Interpretation"))
    
    # Create a table with color bands and their interpretations
    legend_data = [
        ("Percentile Range", "Classification", "Clinical Interpretation"),
        ("> 75", "Above Average", "Strengths"),
        ("25-75", "Average", "Normal functioning"),
        ("9-25", "Low Average", "Mild difficulties"),
        ("2-9", "Low", "Significant difficulties"),
        ("≤ 2", "Very Low", "Severe impairment")
    ]
    
    # Set column widths
    legend_col_widths = [120, 120, 200]
    
    # Create table styles with appropriate colors matching the radar chart
    legend_styles = [
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),  # Make header bold
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        # Color bands matching radar chart
        ('BACKGROUND', (0, 1), (-1, 1), '#b3e6b3'),  # Above average (> 75)
        ('BACKGROUND', (0, 2), (-1, 2), '#ccffcc'),  # Average (25-75)
        ('BACKGROUND', (0, 3), (-1, 3), '#ffff99'),  # Low average (9-25)
        ('BACKGROUND', (0, 4), (-1, 4), '#ffcc99'),  # Low (2-9)
        ('BACKGROUND', (0, 5), (-1, 5), '#ff9999'),  # Very low (≤ 2)
    ]
    
    legend_table = Table(legend_data, colWidths=legend_col_widths)
    legend_table.setStyle(TableStyle(legend_styles))
    elements.append(legend_table)
    elements.append(Spacer(1, 18))

    # Subtest Results Table - Nested by test
    elements.append(create_section_title("Subtest Results"))
    if data["subtests"]:
        grouped = defaultdict(list)
        for row in data["subtests"]:
            # Extract data with the new schema (includes is_valid at row[7])
            subtest_name = row[2]
            metric = row[3]
            score = row[4]
            std_score = row[5]
            percentile = row[6]
            is_valid = row[7] if len(row) > 7 else 1  # Default to valid if column doesn't exist
            
            # Store validity with the test data
            grouped[subtest_name].append((metric, score, std_score, percentile, is_valid))

        table_data = []
        style = [
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),  # Make headers bold
        ]

        row_idx = 0
        for test_name, rows in grouped.items():
            # Check if any metrics in this test are invalid - is_valid is the 5th element (index 4)
            # Handle potential string representations of validity
            test_is_valid = all(str(is_valid).strip().lower() in ['1', 'yes', 'valid'] 
                                for _, _, _, _, is_valid in rows)
            
            # Test header row - mark invalid tests
            test_display_name = test_name
            if not test_is_valid:
                test_display_name += " (INVALID)"
                # Add red background for invalid tests
                style.append(('BACKGROUND', (0, row_idx), (-1, row_idx), colors.lightcoral))
            
            table_data.append([test_display_name])
            style.append(('SPAN', (0, row_idx), (-1, row_idx)))
            style.append(('FONTNAME', (0, row_idx), (-1, row_idx), 'Helvetica-Bold'))
            row_idx += 1

            # Column header
            table_data.append(['Metric', 'Score', 'Standard', 'Percentile'])
            style.append(('BACKGROUND', (0, row_idx), (-1, row_idx), colors.grey))
            style.append(('TEXTCOLOR', (0, row_idx), (-1, row_idx), colors.whitesmoke))
            style.append(('FONTNAME', (0, row_idx), (-1, row_idx), 'Helvetica-Bold'))
            row_idx += 1

            # Subtest metrics
            for metric, score, std, perc, is_valid in rows:
                try:
                    perc = int(perc) if perc is not None else None
                    
                    # Add the row data
                    table_data.append([metric, score, std, perc])
                    
                    # Apply color coding based on percentile value
                    valid_str = str(is_valid).strip().lower()
                    if valid_str in ['1', 'yes', 'valid', 'true']:
                        bg_color = get_percentile_color(perc)
                        style.append(('BACKGROUND', (0, row_idx), (-1, row_idx), bg_color))
                    elif is_valid == 0 or valid_str in ['0', 'no', 'false', 'invalid']:
                        style.append(('BACKGROUND', (0, row_idx), (-1, row_idx), colors.lightcoral))
                        
                except Exception as e:
                    print(f"[ERROR] Invalid percentile: {perc} for metric {metric}, error: {e}")
                    # Still add the row even if coloring fails
                    table_data.append([metric, score, std, perc])
                row_idx += 1

        # Set column widths to better fit the content
        col_widths = [180, 80, 100, 80]  # Match cognitive scores table
        table = Table(table_data, colWidths=col_widths)
        table.setStyle(TableStyle(style))
        elements.append(table)
        elements.append(Spacer(1, 12))

    # Add SAT Speed-Accuracy Plot after subtest results
    if "patient" in data and data["patient"] and data["patient"][0]:
        elements.append(create_section_title("Speed-Accuracy Tradeoff Analysis"))
        
        try:
            # Get patient ID from the data
            patient_id = data["patient"][0]
            
            # Generate the SAT speed-accuracy chart
            sat_chart = create_sat_speed_accuracy_chart(patient_id, db_path='cognitive_analysis.db')
            
            if sat_chart:
                # Add the chart to the report
                elements.append(Image(sat_chart, width=450, height=300))
                elements.append(Paragraph("This chart shows the relationship between reaction time and errors on the Shifting Attention Test (SAT). The red line represents the overall population trend. The blue point shows this patient's position relative to the trend line.", styles['Normal']))
                elements.append(Paragraph("Interpretation: Faster reaction times (lower scores) with fewer errors (lower scores) indicate better performance. Positions below the trend line suggest better-than-average accuracy for the given speed.", styles['Normal']))
            else:
                elements.append(Paragraph("SAT speed-accuracy data not available for this patient.", styles['Normal']))
        except Exception as e:
            print(f"[ERROR] Could not generate SAT speed-accuracy chart: {e}")
            elements.append(Paragraph("Could not generate SAT speed-accuracy chart due to an error.", styles['Normal']))
        
        elements.append(Spacer(1, 12))
    
    elements.append(PageBreak())  # Add page break before ASRS section
     
    #DSM 5 diagnosis from ASRS
    asrs_responses = {row[2]: row[4] for row in data["asrs"]}
    elements += create_asrs_dsm_section(asrs_responses)

    #NPQ
    elements += create_npq_section(data)

    # Domain Explanation Page
    elements.append(PageBreak())  # Start explanations on a new page
    domain_explanation_flowables = create_domain_explanation_page(styles)
    elements.extend(domain_explanation_flowables)
    elements.append(PageBreak())  # End explanations with a page break

    doc.build(elements, onFirstPage=draw_logo)

    print(f"[INFO] Report saved to {output_path}")