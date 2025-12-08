#!/bin/bash

# Script: random_number_generator.sh
# Description: Extracts identifiers from first column (screening_id) and adds random day offset (±3 years)

echo "======================================================================"
echo "Random Number Generator"

# Check if input file is provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 <random_number_input_csv_file> <random_number_output_csv_file>"
    echo "Example: $0 random_number_input.csv random_number_output.csv"
    exit 1
fi

INPUT_FILE="$1"
OUTPUT_FILE="${2:-random_number_output.csv}"

# Check if input file exists
if [ ! -f "$INPUT_FILE" ]; then
    echo "Error: Input file '$INPUT_FILE' not found"
    exit 1
fi

# Extract identifiers from the first column (excluding header)
# First column contains screening_id directly
identifiers=()
while IFS=, read -r first_col rest || [ -n "$first_col" ]; do
    # Skip header line
    if [[ "$first_col" == "screening_id" ]]; then
        continue
    fi
    
    # Skip empty lines
    if [ -n "$first_col" ]; then
        # Use the screening_id directly as the identifier
        # identifier="$first_col"
        # Sunghyun changed this code to fix the skipping issue
        identifier="${first_col//$'\r'/}"
        identifiers+=("$identifier")
    fi
done < "$INPUT_FILE"

# Get unique identifiers
unique_identifiers=$(printf '%s\n' "${identifiers[@]}" | sort | uniq)

echo "Found $(echo "$unique_identifiers" | wc -l) unique identifiers"

# Create output file with headers
echo "patient_identifier,random_number" > "$OUTPUT_FILE"

# Generate random numbers for each unique identifier
while IFS= read -r identifier; do
    # Skip empty lines
    if [ -n "$identifier" ]; then
        # Generate random number between -1095 and +1095 (±3 years in days)
        # Range: -1095 to +1095, total span of 2191 values
        random_days=$((RANDOM % 2191 - 1095))
        
        # Write to output file
        # echo "$identifier,$random_days" >> "$OUTPUT_FILE"
        # Sunghyun Changed the code:
        printf "%s,%s\n" "$identifier" "$random_days" >> "$OUTPUT_FILE"
    fi
done <<< "$unique_identifiers"

echo "Processing complete! Output saved to: $OUTPUT_FILE"
echo "Random day offsets range: -1095 to +1095 days (±3 years)"
echo "======================================================================"
echo ""
