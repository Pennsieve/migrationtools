#!/bin/bash

# Step 1: run random_number_generator.sh to generate random day offsets for each patient identifier
# Usage: ./random_number_generator.sh <input csv with patient identifiers> <output csv with patient identifiers and random offsets within ±3 years>
./random_number_generator.sh random_number_input.csv random_number_output.csv

# Step 2: run batch_process_edf.py (within which modify_edf_dates.py would be pulled) to process all EDF files with the generated random offsets
# Usage: python python batch_process_edf.py <csv file from random_number_generator.sh> <edf directory> [output csv with original and new edf datetime] [edf output directory]
python3 modify_edf_dates.py --input-dir origin/ --random-csv random_number_output.csv \
                                --output-dir input/ --output-csv validation_edf.csv

# Step 3: run update_xml_createtime.py to update the CreateTime in XML files based on the csv yielded from previous step
# Usage: python update_xml_createtime.py <csv with original and new edf datetime from batch_process_edf.py> <xml directory> [xml output directory]
python3 update_xml.py --input-dir origin/ --edf-csv validation_edf.csv \
                            --output-dir input/ --output-csv validation_edf_xml.csv


