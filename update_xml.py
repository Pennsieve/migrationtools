#!/usr/bin/env python3

"""
Script: update_xml.py
Description: Removes createTime, annotator, creatorId, and channels from XML annotation files
             and updates the datetime_edf.csv with annotator, creatorId, and layer information.

Usage: python update_xml.py --input-dir <xml_dir> --edf-csv <datetime_edf.csv> \
                             --output-dir <output_dir> --output-csv <validation_edf_xml.csv>

Arguments:
    --input-dir: Directory containing XML annotation files
    --edf-csv: Input CSV file from modify_edf_dates.py (with patient_identifier, original_date, new_date)
    --output-dir: Directory to save updated XML files
    --output-csv: Output CSV file with added annotator, creatorId, and more_than_one_layer columns
"""

import sys
import os
import csv
import argparse
import glob
import re
import xml.etree.ElementTree as ET


# ==== Helper functions to match the patient id from xml filename and from edf csv ==== 
def extract_patient_id_from_filename(filename):
    """Extract patient ID from XML filename format PRV-<site>-<patient_id>-<age>-annotations.xml"""
    # Pattern: PRV-XXX-XXXX-XX-annotations.xml where XXXX is the patient identifier
    # pattern = r'PRV-[^-]+-([^-]+)-[^-]+-annotations\.xml'
    pattern = r'^PRV-([^-]+)-[^-]+(?:-[^-]+)?-annotations\.xml'
    match = re.search(pattern, filename)
    
    if match:
        return match.group(1).strip()
    else:
        print(f"Warning: Could not extract patient ID from filename '{filename}'")
        return None


def read_edf_csv(csv_file):
    """Read the datetime_edf CSV and create lookup dictionary"""
    lookup = {}
    csv_data = []
    
    try:
        with open(csv_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                csv_data.append(row)
                patient_id = row['patient_identifier'].strip()
                lookup[patient_id] = {
                    'original_date': row['original_date'],
                    'new_date': row['new_date']
                }
        return lookup, csv_data
    except FileNotFoundError:
        print(f"Error: CSV file '{csv_file}' not found")
        sys.exit(1)
    except KeyError as e:
        print(f"Error: CSV file missing required column: {e}")
        sys.exit(1)


# ==== Main fuctions ====
def process_xml_file(xml_file, patient_id, output_dir):
    """
    Process XML file to:
    1. Remove createTime, annotator, creatorId, and channels from all annotations
    2. Extract annotator, creatorId, and layer information
    3. Return metadata about the file
    """
    
    try:
        # First parse to extract metadata
        tree = ET.parse(xml_file)
        root = tree.getroot()
        
        # Track metadata
        annotators = set()
        creator_ids = set()
        layers = set()
        first_annotator = None
        first_creator_id = None
        
        # Find all annotation elements
        annotations = root.findall('annotation')
        
        if not annotations:
            return None
        
        # Extract metadata
        for annotation in annotations:
            if 'annotator' in annotation.attrib:
                annotator = annotation.attrib['annotator']
                annotators.add(annotator)
                if first_annotator is None:
                    first_annotator = annotator
            
            if 'creatorId' in annotation.attrib:
                creator_id = annotation.attrib['creatorId']
                creator_ids.add(creator_id)
                if first_creator_id is None:
                    first_creator_id = creator_id
            
            if 'layer' in annotation.attrib:
                layer = annotation.attrib['layer']
                layers.add(layer)
        
        # Now read the file as text and remove attributes/elements while preserving formatting
        with open(xml_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Remove createTime attribute (with various spacing/newline patterns)
        content = re.sub(r'\s+createTime="[^"]*"', '', content)
        
        # Remove annotator attribute
        content = re.sub(r'\s+annotator="[^"]*"', '', content)
        
        # Remove creatorId attribute
        content = re.sub(r'\s+creatorId="[^"]*"', '', content)
        
        # Remove entire <channels>...</channels> blocks (including nested content)
        # This pattern handles multi-line channels elements
        content = re.sub(r'\s*<channels>.*?</channels>\s*', '\n    ', content, flags=re.DOTALL)
        
        # Write the updated XML to output directory
        os.makedirs(output_dir, exist_ok=True)
        filename = os.path.basename(xml_file)
        output_file = os.path.join(output_dir, filename)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # Determine if there are multiple layers
        more_than_one_layer = 'yes' if len(layers) > 1 else 'no'
        
        return {
            'annotator': first_annotator or '',
            'creatorId': first_creator_id or '',
            'more_than_one_layer': more_than_one_layer,
            'output_file': output_file
        }
        
    except ET.ParseError as e:
        print(f"  Error parsing XML: {e}")
        return None
    except Exception as e:
        print(f"  Unexpected error: {e}")
        return None


def process_directory(input_dir, edf_csv, output_dir, output_csv):
    """Process all XML files in input directory and update the CSV"""
    
    # Read EDF CSV data
    lookup, csv_data = read_edf_csv(edf_csv)
    print(f"Loaded {len(lookup)} patient records from CSV")
    
    # Find all XML annotation files in input directory
    xml_pattern = os.path.join(input_dir, "*-annotations.xml")
    xml_files = glob.glob(xml_pattern)
    
    if not xml_files:
        print(f"No XML annotation files found in {input_dir}")
        return
    
    print(f"Found {len(xml_files)} XML annotation files to process")
    
    # Store XML metadata for each patient
    xml_metadata = {}
    processed_count = 0
    skipped_count = 0
    
    # Process each XML file
    for xml_file in sorted(xml_files):
        filename = os.path.basename(xml_file)
        print(f"\nProcessing: {filename}")
        
        # Extract patient ID from filename
        patient_id = extract_patient_id_from_filename(filename)
        
        if patient_id is None:
            # Sunghyun deleted weird not supported character.
            print(f"Skipped: Could not extract patient ID from filename")
            skipped_count += 1
            continue
                
        # Check if patient ID exists in EDF CSV
        if patient_id not in lookup:
            print(f"Skipped: Patient ID '{patient_id}' not found in datetime_edf CSV")
            skipped_count += 1
            continue
        
        # Process the XML file
        result = process_xml_file(xml_file, patient_id, output_dir)
        
        if result:
            xml_metadata[patient_id] = result
            processed_count += 1
        else:
            print(f"Failed to process")
            skipped_count += 1
    
    print(f"\nProcessing Summary:")
    print(f"  Total XML files: {len(xml_files)}")
    print(f"  Successfully processed: {processed_count}")
    print(f"  Skipped: {skipped_count}")
    
    # Add new columns to CSV data
    for row in csv_data:
        patient_id = row['patient_identifier']
        
        if patient_id in xml_metadata:
            metadata = xml_metadata[patient_id]
            row['annotator'] = metadata['annotator']
            row['creatorId'] = metadata['creatorId']
            row['more_than_one_layer'] = metadata['more_than_one_layer']
        else:
            row['annotator'] = ''
            row['creatorId'] = ''
            row['more_than_one_layer'] = ''
    
    # Write updated CSV (filter to only include desired columns)
    with open(output_csv, 'w', newline='') as f:
        fieldnames = ['patient_identifier', 'annotator', 'creatorId', 'more_than_one_layer']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        # Filter each row to only include the desired fields
        filtered_rows = []
        for row in csv_data:
            filtered_row = {field: row.get(field, '') for field in fieldnames}
            filtered_rows.append(filtered_row)
        
        writer.writerows(filtered_rows)


def main():
    parser = argparse.ArgumentParser(
        description='Remove identifying information from XML annotation files and update validation CSV',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python update_xml.py --input-dir ./input --edf-csv datetime_edf.csv \\
                       --output-dir ./output --output-csv validation_edf_xml.csv
        """
    )
    
    parser.add_argument('--input-dir', required=True,
                        help='Directory containing XML annotation files')
    parser.add_argument('--edf-csv', required=True,
                        help='Input datetime_edf CSV file from modify_edf_dates.py')
    parser.add_argument('--output-dir', required=True,
                        help='Directory to save updated XML files')
    parser.add_argument('--output-csv', required=True,
                        help='Output CSV file with annotator, creatorId, and more_than_one_layer columns')
    
    args = parser.parse_args()
    
    # Validate input directory exists
    if not os.path.exists(args.input_dir):
        print(f"Error: Input directory '{args.input_dir}' does not exist")
        sys.exit(1)
    
    # Validate EDF CSV exists
    if not os.path.exists(args.edf_csv):
        print(f"Error: EDF CSV file '{args.edf_csv}' does not exist")
        sys.exit(1)
    
    print("="*80)
    print("XML Annotation Updater")
    print("")
    
    # Process all files
    process_directory(args.input_dir, args.edf_csv, args.output_dir, args.output_csv)
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
