#!/usr/bin/env python3

"""
Script: modify_edf_dates.py
Description: Modifies EDF file start dates based on random day offsets from CSV.
             Processes all EDF files in an input directory and outputs date-shifted files
             to an output directory with a validation CSV.

Usage: python modify_edf_dates.py --input-dir <input_dir> --random-csv <random_csv> 
                                   --output-dir <output_dir> --output-csv <output_csv>

Arguments:
    --input-dir: Directory containing EDF files to process
    --random-csv: CSV file with patient identifiers and random day offsets
    --output-dir: Directory to save date-shifted EDF files
    --output-csv: CSV file to save validation data (patient_identifier, original_date, new_date)
"""

import sys
import csv
import argparse
import glob
import re
from datetime import datetime, timedelta
import os


# ==== Functions to parse EDF date from bytes 168-175 ====
def parse_edf_date(date_str):
    """Parse EDF date format (dd.mm.yy) to datetime object."""
    date_str = date_str.strip()
    day, month, year = date_str.split('.')
    
    # Handle 2-digit year (EDF uses yy format)
    year_int = int(year)
    if year_int >= 85:  # Assume 1985-1999
        full_year = 1900 + year_int
    else:  # Assume 2000-2084
        full_year = 2000 + year_int
    
    return datetime(full_year, int(month), int(day))

def parse_edf_time(time_str):
    """Parse EDF time format (hh.mm.ss) to time components."""
    time_str = time_str.strip()
    hour, minute, second = time_str.split('.')
    return int(hour), int(minute), int(second)

def parse_edf_datetime(date_str, time_str):
    """Parse EDF date and time to datetime object."""
    date_obj = parse_edf_date(date_str)
    hour, minute, second = parse_edf_time(time_str)
    return datetime(date_obj.year, date_obj.month, date_obj.day, hour, minute, second)


# ==== Functions to re-format EDF date for bytes 168-175 and 88-167 ====
def format_edf_date(date_obj):
    """Format datetime object to EDF date format (dd.mm.yy)."""
    # EDF uses 2-digit year
    year_2digit = date_obj.year % 100
    return f"{date_obj.day:02d}.{date_obj.month:02d}.{year_2digit:02d}"

def format_startdate_field(date_obj):
    """Format datetime object to 'Startdate DD-MMM-YYYY' format for recording identification field."""
    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
              'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    month_name = months[date_obj.month - 1]
    return f"Startdate {date_obj.day:02d}-{month_name}-{date_obj.year}"


# ==== Helper functions to match patient ids in CSV and EDF filenames ===== 
def read_csv_lookup(csv_file):
    """Read the random_number CSV and create lookup dictionary."""
    lookup = {}
    try:
        with open(csv_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                patient_id = row['patient_identifier'].strip()
                random_days = int(row['random_number'])
                lookup[patient_id] = random_days
        return lookup
    except FileNotFoundError:
        print(f"Error: CSV file '{csv_file}' not found")
        sys.exit(1)
    except KeyError as e:
        print(f"Error: CSV file missing required column: {e}")
        sys.exit(1)

def extract_patient_id_from_filename(filename):
    """Extract patient ID from EDF filename format PRV-<site>-<patient_id>-<age>.edf"""
    # Pattern: PRV-XXX-XXXX-XX.edf where XXXX is the patient identifier
    # pattern = r'PRV-[^-]+-([^-]+)-[^-]+\.edf'
    # Sunghyun updated the pattern
    pattern = r'^PRV-([^-]+)-[^-]+(?:-[^-]+)?\.edf'
    match = re.search(pattern, filename)
    
    if match:
        return match.group(1).strip()
    else:
        print(f"Warning: Could not extract patient ID from filename '{filename}'")
        return None


# ==== Main functions to loop through all files and modify EDF headers ====
def modify_edf_header(edf_file, patient_id, random_days, output_dir):
    """Modify EDF header with new start date. Returns info dict for CSV output."""
    
    if not os.path.exists(edf_file):
        print(f"Error: EDF file '{edf_file}' not found")
        return None
    
    # Read the entire file
    with open(edf_file, 'rb') as f:
        content = bytearray(f.read())
    
    # EDF header structure (first 256 bytes minimum)
    # Bytes 0-7: Version
    # Bytes 8-87: Local patient identification (80 bytes)
    # Bytes 88-167: Local recording identification (80 bytes) - contains "Startdate DD-MMM-YYYY"
    # Bytes 168-175: Startdate (dd.mm.yy) (8 bytes)
    # Bytes 176-183: Starttime (hh.mm.ss) (8 bytes)
    
    if len(content) < 256:
        print(f"Error: EDF file '{edf_file}' is too small (< 256 bytes)")
        return None
    
    # Extract current start date and time from bytes 168-183
    start_date_str = content[168:176].decode('ascii', errors='ignore')
    start_time_str = content[176:184].decode('ascii', errors='ignore')
    
    try:
        original_datetime = parse_edf_datetime(start_date_str, start_time_str)
    except Exception as e:
        print(f"Error parsing datetime '{start_date_str} {start_time_str}': {e}")
        return None
    
    # Calculate new date (keeping the same time)
    new_date = original_datetime.date() + timedelta(days=random_days)
    new_datetime = datetime.combine(new_date, original_datetime.time())
    
    # Format new date for EDF (time remains unchanged)
    new_date_str = format_edf_date(new_datetime)
    
    # Modify the date field in bytes 168-175
    # Ensure date is exactly 8 bytes (padded with spaces if needed)
    new_date_bytes = new_date_str.ljust(8).encode('ascii')
    content[168:176] = new_date_bytes
    
    # Modify the "Startdate DD-MMM-YYYY" field in the recording identification (bytes 88-167)
    recording_id = content[88:168].decode('ascii', errors='ignore')
    
    # Replace the Startdate field with the new date
    new_startdate_str = format_startdate_field(new_datetime)
    
    # The recording identification field is 80 bytes, pad with spaces
    # Keep any text after the date if it exists, or just pad with spaces
    if 'Startdate' in recording_id:
        # Replace just the Startdate portion, preserving any trailing content
        new_recording_id = new_startdate_str.ljust(80)
    else:
        # If no Startdate found, just use the new one
        new_recording_id = new_startdate_str.ljust(80)
    
    new_recording_id_bytes = new_recording_id[:80].encode('ascii', errors='replace')
    content[88:168] = new_recording_id_bytes
    
    # Write to output file
    os.makedirs(output_dir, exist_ok=True)
    filename = os.path.basename(edf_file)
    output_file = os.path.join(output_dir, filename)
    
    with open(output_file, 'wb') as f:
        f.write(content)
        
    # Return information for CSV output
    return {
        'patient_identifier': patient_id,
        'original_date': original_datetime.strftime('%Y-%m-%d'),
        'new_date': new_datetime.strftime('%Y-%m-%d'),
        'random_days_offset': random_days,
                'output_file': output_file
    }


def process_directory(input_dir, random_csv, output_dir, output_csv):
    """Process all EDF files in input directory and generate validation CSV."""
    
    # Read CSV lookup table
    lookup = read_csv_lookup(random_csv)
    print(f"Loaded {len(lookup)} patient mappings from CSV")
    
    # Find all EDF files in input directory
    edf_pattern = os.path.join(input_dir, "*.edf")
    edf_files = glob.glob(edf_pattern)
    
    if not edf_files:
        print(f"No EDF files found in {input_dir}")
        return
    
    print(f"Found {len(edf_files)} EDF files to process")
    
    # Store results for CSV output
    results = []
    processed_count = 0
    skipped_count = 0
    
    # Process each EDF file
    for edf_file in sorted(edf_files):
        filename = os.path.basename(edf_file)
        print(f"\nProcessing: {filename}")
        
        # Extract patient ID from filename
        patient_id = extract_patient_id_from_filename(filename)
        
        if patient_id is None:
            print(f"Skipped: Could not extract patient ID from filename")
            skipped_count += 1
            continue
                
        # Check if patient ID exists in lookup
        if patient_id not in lookup:
            print(f"Skipped: Patient ID '{patient_id}' not found in random number CSV")
            skipped_count += 1
            continue
        
        random_days = lookup[patient_id]
        print(f"  Random offset: {random_days} days")
        
        # Modify EDF header
        result = modify_edf_header(edf_file, patient_id, random_days, output_dir)
        
        if result:
            print(f"  Original date: {result['original_date']}")
            print(f"  New date: {result['new_date']}")
            results.append(result)
            processed_count += 1
        else:
            print(f"Failed to process")
            skipped_count += 1
    
    print(f"\nProcessing Summary:")
    print(f"Total files: {len(edf_files)}")
    print(f"Successfully processed: {processed_count}")
    print(f"Skipped: {skipped_count}")
    
    # Write validation CSV
    if results:
        with open(output_csv, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['patient_identifier', 'original_date', 'new_date'])
            writer.writeheader()
            for result in results:
                writer.writerow({
                    'patient_identifier': result['patient_identifier'],
                    'original_date': result['original_date'],
                    'new_date': result['new_date']
                })

def main():
    parser = argparse.ArgumentParser(
        description='Modify EDF file dates based on random day offsets',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python modify_edf_dates.py --input-dir ./input --random-csv random_number_output.csv \\
                              --output-dir ./output --output-csv datetime_edf.csv
        """
    )
    
    parser.add_argument('--input-dir', required=True,
                        help='Directory containing EDF files to process')
    parser.add_argument('--random-csv', required=True,
                        help='CSV file with patient identifiers and random day offsets')
    parser.add_argument('--output-dir', required=True,
                        help='Directory to save date-shifted EDF files')
    parser.add_argument('--output-csv', required=True,
                        help='CSV file to save validation data (patient_identifier, original_date, new_date)')
    
    args = parser.parse_args()
    
    # Validate input directory exists
    if not os.path.exists(args.input_dir):
        print(f"Error: Input directory '{args.input_dir}' does not exist")
        sys.exit(1)
    
    # Validate random CSV exists
    if not os.path.exists(args.random_csv):
        print(f"Error: Random number CSV '{args.random_csv}' does not exist")
        sys.exit(1)
    
    print("="*80)
    print("EDF Date Modifier")
    print("")
    
    # Process all files
    process_directory(args.input_dir, args.random_csv, args.output_dir, args.output_csv)
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
