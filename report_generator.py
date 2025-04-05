import matplotlib.pyplot as plt
import numpy as np
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
from io import BytesIO
from asrs_dsm_mapper import create_asrs_dsm_section
from reportlab.lib.units import mm, inch
import sqlite3
import pandas as pd
import os
from scipy import stats
import seaborn as sns
from collections import defaultdict
import logging

# Set up logging
logging.basicConfig(
    filename='report_generation.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filemode='w'  # Overwrite existing log file
)

def debug_log(message):
    """Log debug message to file and print to console"""
    logging.debug(message)
    print(message)

#python generate_report.py 34766-20231015201357.pdf --import

def create_radar_chart(scores, invalid_domains=None):
    """
    Create a radar chart of cognitive scores.
    
    Args:
        scores: Dict mapping domain names to scores
        invalid_domains: List of domain names that are invalid
    """
    if invalid_domains is None:
        invalid_domains = []
        
    labels = [
        "Verbal Memory", "Visual Memory", "Psychomotor Speed",
        "Reaction Time", "Complex Attention", "Cognitive Flexibility",
        "Processing Speed", "Executive Function"
    ]
    
    # Print the scores we have
    print("\nScores passed to radar chart:")
    for label in labels:
        value = scores.get(label, "MISSING")
        print(f"  {label}: {value}")
    
    values = [scores.get(label, 0) for label in labels]
    values += values[:1]  # loop closure
    
    # Create a mask for invalid domains
    invalid_mask = [label in invalid_domains for label in labels]
    invalid_mask += invalid_mask[:1]  # loop closure

    angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(10, 10), subplot_kw=dict(polar=True))
    ax.set_theta_offset(np.pi / 2)  # Top = 12 o'clock
    ax.set_theta_direction(-1)      # Clockwise

    # Draw colored background bands for standard deviation bands
    bands = [2, 9, 25, 75, 101]  # very low, low, low average, average, above average
    colors_band = ['#ff9999', '#ffcc99', '#ffff99', '#ccffcc', '#b3e6b3']

    for i in range(len(bands)-1):
        ax.fill_between(angles, bands[i], bands[i+1], color=colors_band[i], alpha=0.5)

    # Plot the data points
    ax.plot(angles, values, color='black', linewidth=2)
    ax.fill(angles, values, color='deepskyblue', alpha=0.6)
    
    # Mark invalid domains with red X
    for i, (angle, value, is_invalid) in enumerate(zip(angles[:-1], values[:-1], invalid_mask[:-1])):
        if is_invalid:
            # Plot a red X over invalid points
            marker_size = 200
            ax.scatter(angle, value, s=marker_size, color='red', marker='x', linewidth=2)
    
    # Add labels and scores outside the plot
    for angle, value, label, is_invalid in zip(angles[:-1], values[:-1], labels, invalid_mask[:-1]):
        # Convert angle to degrees for easier handling
        deg_angle = np.degrees(angle)
        
        # Use fixed positions for each label based on its index
        # This maps each domain to a specific position around the chart
        idx = labels.index(label)
        # Reorder positions to match the angular placement of the original labels list
        positions = [
            (0.5, 0.95),   # Top (for Verbal Memory @ labels[0]/angle 0)
            (0.85, 0.85),  # Top right (for Visual Memory @ labels[1]/angle 1)
            (0.95, 0.5),   # Right (for Psychomotor Speed @ labels[2]/angle 2)
            (0.85, 0.15),  # Bottom right (for Reaction Time @ labels[3]/angle 3)
            (0.5, 0.05),   # Bottom (for Complex Attention @ labels[4]/angle 4)
            (0.15, 0.15),  # Bottom left (for Cognitive Flexibility @ labels[5]/angle 5)
            (0.05, 0.5),   # Left (for Processing Speed @ labels[6]/angle 6)
            (0.15, 0.85),  # Top left (for Executive Function @ labels[7]/angle 7)
        ]
        
        # Get the position for this label
        pos_x, pos_y = positions[idx]
        
        # Convert to data coordinates
        # This is a bit of a hack, but it works for placing text outside the plot
        x = pos_x * 120
        y = pos_y * 120
        
        # Adjust text alignment based on position
        ha = 'center'
        va = 'center'
        
        # Fine-tune alignments based on position
        if pos_x < 0.2:  # Left side
            ha = 'right'
        elif pos_x > 0.8:  # Right side
            ha = 'left'
            
        if pos_y < 0.2:  # Bottom
            va = 'top'
        elif pos_y > 0.8:  # Top
            va = 'bottom'
        
        # Create label with domain name and score
        score_text = f"{label}\n{value}%"
        if is_invalid:
            score_text += " (INVALID)"
            
        # Place the text at the calculated position
        ax.text(
            angle, 
            110,  # Fixed radius for all labels
            score_text,
            horizontalalignment=ha,
            verticalalignment=va,
            fontsize=12
        )
    
    # Set ticks and labels
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels([])  # No labels on the spokes
    
    # Set y-ticks (percentile bands)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.set_yticklabels(['0', '25', '50', '75', '100'], fontsize=10)
    ax.set_rlabel_position(180)  # Move radial labels away from plotted line
    
    # Add percentile band labels
    band_labels = ['Very Low', 'Low', 'Low Average', 'Average', 'High Average', 'High', 'Very High']
    band_positions = [5, 16, 37, 63, 84, 95]  # Midpoints of bands
    
    for i, (label, pos) in enumerate(zip(band_labels, [1] + band_positions + [99])):
        if i == 0:  # Very Low
            ax.text(np.radians(90), pos, label, ha='center', va='center', fontsize=8, color='darkred')
        elif i == len(band_labels) - 1:  # Very High
            ax.text(np.radians(90), pos, label, ha='center', va='center', fontsize=8, color='darkgreen')
        else:
            ax.text(np.radians(90), pos, label, ha='center', va='center', fontsize=8)
    
    # Add title
    plt.title('Cognitive Domain Scores', size=20, y=1.1)
    
    # Add legend for invalid domains if any
    if any(invalid_mask[:-1]):
        plt.figtext(0.5, 0.01, "Note: Domains marked (INVALID) failed validity checks", 
                   ha="center", fontsize=10, bbox={"facecolor":"orange", "alpha":0.2, "pad":5})
    
    # Set limits
    ax.set_ylim(0, 100)
    
    # Save to BytesIO
    img_data = BytesIO()
    plt.savefig(img_data, format='png', dpi=150, bbox_inches='tight')
    img_data.seek(0)
    plt.close()
    
    return img_data


from reportlab.platypus import Table, TableStyle
from reportlab.lib import colors

def create_npq_section(data):
    # Extract NPQ scores and questions
    npq_scores = data.get('npq_scores', [])
    npq_questions = data.get('npq_questions', [])
    
    if not npq_scores and not npq_questions:
        return [Paragraph("No NPQ data available", getSampleStyleSheet()['Normal'])]
    
    styles = getSampleStyleSheet()
    elements = []
    
    # Add NPQ section title
    elements.append(Paragraph("<b>Neurobehavioral Symptom Questionnaire (NPQ)</b>", styles['Heading2']))
    elements.append(Spacer(1, 10))
    
    # Add disclaimer
    disclaimer_text = """<i>The NPQ is a screening tool and not a diagnostic instrument. Results should be interpreted by a qualified healthcare professional in conjunction with clinical evaluation.</i>"""
    elements.append(Paragraph(disclaimer_text, styles['Normal']))
    elements.append(Spacer(1, 10))
    
    def severity_color(severity):
        """Return color based on severity level"""
        if severity == "Severe":
            return colors.red
        elif severity == "Moderate":
            return colors.orange
        elif severity == "Mild":
            return colors.yellow
        else:
            return colors.white
    
    def section_block(title, domains):
        """Create a section block for a group of related domains"""
        block = []
        block.append(Paragraph(f"<b>{title}</b>", styles['Heading3']))
        block.append(Spacer(1, 5))
        
        for domain, severity in domains:
            color = severity_color(severity)
            block.append(
                Paragraph(
                    f"<font color='{colors.black}'><b>{domain}:</b> <font bgcolor='{color}'>{severity}</font></font>",
                    styles['Normal']
                )
            )
        
        block.append(Spacer(1, 10))
        return block
    
    # Organize domains by category
    adhd_domains = []
    anxiety_domains = []
    mood_domains = []
    asd_domains = []
    other_domains = []
    
    # Process NPQ scores
    for score in npq_scores:
        # Assuming format: (patient_id, domain, raw_score, t_score, severity)
        if len(score) >= 5:
            domain = score[1]
            severity = score[4] if score[4] else "Not Available"
            
            # Categorize domains
            domain_lower = domain.lower()
            if "adhd" in domain_lower or "attention" in domain_lower or "hyperactivity" in domain_lower or "impulsivity" in domain_lower:
                adhd_domains.append((domain, severity))
            elif "anxiety" in domain_lower or "panic" in domain_lower or "phobia" in domain_lower or "ocd" in domain_lower:
                anxiety_domains.append((domain, severity))
            elif "depress" in domain_lower or "mood" in domain_lower or "mania" in domain_lower or "bipolar" in domain_lower:
                mood_domains.append((domain, severity))
            elif "autism" in domain_lower or "asd" in domain_lower or "asperger" in domain_lower:
                asd_domains.append((domain, severity))
            else:
                other_domains.append((domain, severity))
    
    # Add color legend
    legend_data = [
        ["Severity Legend:"],
        [Paragraph("<font bgcolor='%s'>Severe</font>" % colors.red, styles['Normal'])],
        [Paragraph("<font bgcolor='%s'>Moderate</font>" % colors.orange, styles['Normal'])],
        [Paragraph("<font bgcolor='%s'>Mild</font>" % colors.yellow, styles['Normal'])]
    ]
    
    legend_table = Table(legend_data, colWidths=[100])
    legend_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.5, colors.black),
        ('BACKGROUND', (0, 0), (0, 0), colors.lightgrey),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ]))
    
    elements.append(legend_table)
    elements.append(Spacer(1, 15))
    
    # Add each section
    if adhd_domains:
        elements.extend(section_block("ADHD Symptoms", adhd_domains))
    
    if anxiety_domains:
        elements.extend(section_block("Anxiety Symptoms", anxiety_domains))
    
    if mood_domains:
        elements.extend(section_block("Mood Symptoms", mood_domains))
    
    if asd_domains:
        elements.extend(section_block("Autism Spectrum Symptoms", asd_domains))
    
    if other_domains:
        elements.extend(section_block("Other Symptoms", other_domains))
    
    # Add detailed questions table if available
    if npq_questions:
        elements.append(Paragraph("<b>Detailed NPQ Responses</b>", styles['Heading3']))
        elements.append(Spacer(1, 10))
        
        # Organize questions by domain
        questions_by_domain = defaultdict(list)
        for question in npq_questions:
            # Assuming format: (patient_id, domain, question_number, question_text, response)
            if len(question) >= 5:
                domain = question[1]
                question_text = question[3]
                response = question[4]
                questions_by_domain[domain].append((question_text, response))
        
        # Create a table for each domain
        for domain, questions in questions_by_domain.items():
            elements.append(Paragraph(f"<b>{domain}</b>", styles['Heading4']))
            elements.append(Spacer(1, 5))
            
            # Create table data
            table_data = [["Question", "Response"]]
            for question_text, response in questions:
                table_data.append([question_text, response])
            
            # Create table
            table = Table(table_data, colWidths=[400, 50])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ALIGN', (1, 1), (1, -1), 'CENTER'),
            ]))
            
            elements.append(table)
            elements.append(Spacer(1, 15))
    
    return elements

def draw_logo(canvas, doc):
    logo_path = "imgs/LogoWB.png"
    logo_width = 40 * mm
    logo_height = 40 * mm
    x = doc.pagesize[0] - logo_width - 20  # right margin
    y = doc.pagesize[1] - logo_height - 20  # top margin
    canvas.drawImage(logo_path, x, y, width=logo_width, height=logo_height, preserveAspectRatio=True, mask='auto')


def create_section_title(title):
    return Paragraph(f'<b>{title}</b>', getSampleStyleSheet()['Heading2'])


def color_for_percentile(p):
    if p is None:
        return colors.lightgrey
    if p > 74:
        return colors.green
    elif 25 <= p <= 74:
        return colors.lightgreen
    elif 9 <= p < 25:
        return colors.khaki
    elif 2 <= p < 9:
        return colors.orange
    else:
        return colors.red


def get_percentile_color(percentile):
    if percentile is None or percentile == "":
        return colors.white
    try:
        percentile = float(percentile)
        if percentile > 75:
            return colors.HexColor('#b3e6b3')  # Above average (> 75)
        elif percentile >= 25:
            return colors.HexColor('#ccffcc')  # Average (25-75)
        elif percentile >= 9:
            return colors.HexColor('#ffff99')  # Low average (9-25)
        elif percentile >= 2:
            return colors.HexColor('#ffcc99')  # Low (2-9)
        else:
            return colors.HexColor('#ff9999')  # Very low (≤ 2)
    except (ValueError, TypeError):
        return colors.white