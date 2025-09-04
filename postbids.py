#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Feb 18 14:03:26 2025

@author: juliadengler
"""

import os
import mne
import csv
import regex as re
import pandas as pd
import glob
import json
import pyedflib
from datetime import datetime
import shutil 
import argparse
import sys
import logging
import hashlib

SES_IMPLANT_FOLDER = "ses-postimplant"

def parse_arguments():
    """ Parse command line arguments """
    parser = argparse.ArgumentParser(description="Process input folders with a flag for either iEEG or scalp data.")
    
    parser.add_argument('folder1', type=str, help="Path to the subject folder folder")
    parser.add_argument('folder2', type=str, help="Path to the pipeline creation folder")
    parser.add_argument('type', type=str, choices=['ieeg', 'scalp'], help="Flag indicating data type: 'ieeg' or 'scalp'")
    
    # --- edited out by sz on 09/04/25 to remove EPS-related code 
    # parser.add_argument('--eps', type=str, default=None, help="Optional EPS ID (e.g. EPS0000166)")
    
    parser.add_argument('--day', type=str, default=None, help="Session day identifier (e.g. D02)")
    parser.add_argument('--keep-temp', action='store_true', help="If set, will not delete temporary folders after merge")

    args = parser.parse_args()

    if not os.path.isdir(args.folder1) or not os.path.isdir(args.folder2):
        return None
    
    return args


def create_folder_structure(subject_folder, subjectid):
    """ Creates primary and derivative folder structures"""
    os.makedirs(os.path.join(subject_folder, 'primary'), exist_ok=True)
    os.makedirs(os.path.join(subject_folder, 'derivative'), exist_ok=True)
    
    primary_dir = os.path.join(subject_folder, 'primary')
    derivative_dir = os.path.join(subject_folder, 'derivative')
    ## Nested directory is the primary directory than subject folder than session folder 
    nested_dir = os.path.join(primary_dir, f'sub-{subjectid}', SES_IMPLANT_FOLDER)
    
    os.makedirs(nested_dir,exist_ok=True)
    
    return primary_dir, nested_dir, derivative_dir


def create_readme_file(subject_folder):
    """ Makes README.txt file in primary dir"""
    readme_content = '''References ---------- 
    Appelhoff, S., Sanderson, M., Brooks, T., Vliet, M., Quentin, R., Holdgraf, C., Chaumon, M., Mikulan, E., 
    Tavabi, K., Höchenberger, R., Welke, D., Brunner, C., Rockhill, A., Larson, E., Gramfort, A. and Jas, M. 
    (2019). MNE-BIDS: Organizing electrophysiological data into the BIDS format and facilitating their analysis. 
    Journal of Open Source Software 4: (1896). https://doi.org/10.21105/joss.01896'''

    with open(os.path.join(subject_folder, 'README.txt'), 'w') as f:
        f.write(readme_content)

def create_participants_file(subject_folder, primary_dir, pipeline_folder):
    """ Creates participants.tsv file """
    deiddata =  pd.read_csv(os.path.join(pipeline_folder, 'deidentified_data.csv'), encoding='latin1')
    subject_id = re.sub(r"[^0-9]","", os.path.basename(subject_folder.split("_")[0]))
    regex = "^0+(?!$)"
    new_subjid = re.sub(regex, "", subject_id)
    subj_deid = deiddata[deiddata.iloc[:, 0] == new_subjid]
    mri_date = (subj_deid['MRI Date:']).to_string(index = False)
    
    if not subj_deid.empty:
        #print(f"Found '{subject_id}' in de-identified data")
        subj_deid.to_csv(os.path.join(primary_dir,"partcipants.csv"), index=False)
   # else:
        #print(f"'{subject_id}' not found in the first column.")
        
    
    return mri_date
        
def create_dataset_description(primary_dir):
    """ Create dataset_description.json"""
    dataset_description = {
                "Name": "",
                "BIDSVersion": "1.7.0",
                "Description": "",
                "License": "",
                "DatasetType": "raw",
                "Authors": [
                    "[Unspecified]"
                ]
                }
    
    # Writing to json
    with open(os.path.join(primary_dir, "dataset_description.json"), "w") as outfile:
        json.dump(dataset_description, outfile, indent =4)
        

def create_participants_json(primary_dir):
    """ Create participants.json"""
    ## Needs to be improved significantly !!!!
    participantsjson = {
    "participant_id": {
        "Description": "Unique participant identifier"
    },
    "age": {
        "Description": "Age of the participant at time of testing",
        "Units": "years"
    },
    "sex": {
        "Description": "Biological sex of the participant",
        "Levels": {
            "F": "female",
            "M": "male"
        }
    },
    "hand": {
        "Description": "Handedness of the participant",
        "Levels": {
            "R": "right",
            "L": "left",
            "A": "ambidextrous"
        }
    },
    "weight": {
        "Description": "Body weight of the participant",
        "Units": "kg"
    },
    "height": {
        "Description": "Body height of the participant",
        "Units": "m"
    }
}


    # Writing to json
    with open(os.path.join(primary_dir,"partcipants.json"), "w") as outfile:
        json.dump(participantsjson, outfile, indent=4) 
        
def find_files_by_type(folder_path, file_extension):
    """ Find files of a certain type in a directory """
    if not os.path.isdir(folder_path):
        #print(f"Error: Invalid folder path: {folder_path}")
        return []
    
    return glob.glob(os.path.join(folder_path, f"*{file_extension}"))
    

# --------- updated the process_edf_files func to remove eps-related codes by sz 
def process_edf_files(subject_folder, primary_dir, nested_dir, modlevelfolder, nested_name,pipeline_folder):
    """ Creates channels.tsv file for all data """
    
    column_names = ["name","type","units","low_cutoff","high_cutoff","description","sampling_frequency","status","status_description"]
    data = []
    lines = []
    
    channel_data_file = f"{primary_dir.split('/')[-2]}.txt"
    channel_data_path = os.path.join(pipeline_folder, channel_data_file)
    
    """ Process edf files and generate all sidecar files """
    found_files = find_files_by_type(subject_folder +'/', '.mef')
    total_duration = 0
    
    logging.getLogger('pyedflib').setLevel(logging.CRITICAL)
    mne.set_log_level('CRITICAL')
    
    ecognum = 0
    ecgnum = 0
    emgnum = 0
    eegnum = 0
    eognum = 0
    seegnum = 0 

    with open(channel_data_path, 'r') as f:
        
        lines = f.readlines()
        for line in lines:
            line_data = line.split(',')
            channel_name = line_data[0].strip()
            typestr = line_data[1].strip()
            units = line_data[2].strip()
            low_cutoff = line_data[3].strip()
            high_cutoff = line_data[4].strip()
            description = line_data[5].strip()
            samplingfreq = line_data[6].strip()
            data.append([channel_name, typestr, units, low_cutoff, high_cutoff, description, samplingfreq, "good", "n/a"])
        
    file_path = os.path.join(nested_dir, modlevelfolder, nested_name + '_channels.tsv')
    line = lines[0]
    startTime = int(lines[0].split(',')[8])
    endTime = int(lines[0].split(',')[7])
    total_duration = endTime - startTime
    with open(file_path, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(column_names)
        writer.writerows(data)
        
            
    for file in found_files:
        run_number= ""
        nested_path = nested_dir + '/' + modlevelfolder +'/'
        
        # Move edf files
        move_mef_files(file, nested_path + '/', nested_name, run_number)
        
    # Generate iEEG json 
    ieeg_json =  {
        "TaskName": "rest",
        "Manufacturer": "n/a",
        "PowerLineFrequency": "n/a",
        "SamplingFrequency": samplingfreq,
        "SoftwareFilters": "n/a",
        "RecordingDuration": total_duration,
        "RecordingType": "continuous",
        "iEEGReference": "n/a",
        "ECOGChannelCount": ecognum,
        "SEEGChannelCount": seegnum,
        "EEGChannelCount": eegnum,
        "EOGChannelCount": eognum,
        "ECGChannelCount": ecgnum,
        "EMGChannelCount": emgnum,
        "MiscChannelCount": 0,
        "TriggerChannelCount": 0
        }
    
   # with open(os.path.join(nested_dir, modlevelfolder, nested_name + '_' + f'{run_number}_ieeg.json'), 'w') as outfile:
    with open(os.path.join(nested_dir, modlevelfolder, nested_name  + '_ieeg.json'), 'w') as outfile:
        json.dump(ieeg_json, outfile, indent=4)

# def process_edf_files(subject_folder, primary_dir, nested_dir, modlevelfolder, nested_name, eps_string,pipeline_folder):
#     """ Creates channels.tsv file for all data """
    
#     column_names = ["name","type","units","low_cutoff","high_cutoff","description","sampling_frequency","status","status_description"]
#     data = []
#     lines = []
    
#     channel_data_file = f"{primary_dir.split('/')[-2]}.txt"
#     channel_data_path = os.path.join(pipeline_folder, channel_data_file)
    
#     """ Process edf files and generate all sidecar files """
#     found_files = find_files_by_type(subject_folder +'/', '.mef')
#     total_duration = 0
    
#     logging.getLogger('pyedflib').setLevel(logging.CRITICAL)
#     mne.set_log_level('CRITICAL')
    

#     # edf_file = pyedflib.EdfReader(found_files[0])
#     # edffile = mne.io.read_raw_edf(found_files[0])
        
#     ecognum = 0
#     ecgnum = 0
#     emgnum = 0
#     eegnum = 0
#     eognum = 0
#     seegnum = 0 

#     with open(channel_data_path, 'r') as f:
        
#         lines = f.readlines()
#         for line in lines:
#             line_data = line.split(',')
#             channel_name = line_data[0].strip()
#             typestr = line_data[1].strip()
#             units = line_data[2].strip()
#             low_cutoff = line_data[3].strip()
#             high_cutoff = line_data[4].strip()
#             description = line_data[5].strip()
#             samplingfreq = line_data[6].strip()
#             data.append([channel_name, typestr, units, low_cutoff, high_cutoff, description, samplingfreq, "good", "n/a"])
        
#     file_path = os.path.join(nested_dir, modlevelfolder, nested_name + '_channels.tsv')
#     line = lines[0]
#     startTime = int(lines[0].split(',')[8])
#     endTime = int(lines[0].split(',')[7])
#     total_duration = endTime - startTime
#     with open(file_path, 'w', newline='') as csvfile:
#         writer = csv.writer(csvfile)
#         writer.writerow(column_names)
#         writer.writerows(data)
            
#     # edf_file.close()
#     # del edf_file
#     # edffile.close()
#     # del edffile
            
#     for file in found_files:
        
#         # new_bytes = eps_string.encode('utf-8')
#         # size_of_new_bytes = len(new_bytes)

#         # blankbytes = b' ' * (80 - size_of_new_bytes)
#         # final_bytes = new_bytes + blankbytes

#         # with open(file, 'rb+') as f:
#         #     f.seek(8)
#         #     f.write(final_bytes)
            
            
#         # edf_file = pyedflib.EdfReader(file)
#         # edffile = mne.io.read_raw_edf(file)
#         # run_number =get_run_number_from_file(file)
#         run_number= ""
#         # Find duration per edf file and add to overall duration variable 
        
#         # edffile.info['patient_id'] = eps_string

#         # edffile.save(file, overwrite=True)
        
#         nested_path = nested_dir + '/' + modlevelfolder +'/'
        
#         # Move edf files
#         move_mef_files(file, nested_path + '/', nested_name, run_number)
        
#         # edf_file.close()
#         # del edf_file
#         # edffile.close()
#         # del edffile
            
        
#     # Generate iEEG json 
#     ieeg_json =  {
#         "TaskName": "rest",
#         "Manufacturer": "n/a",
#         "PowerLineFrequency": "n/a",
#         "SamplingFrequency": samplingfreq,
#         "SoftwareFilters": "n/a",
#         "RecordingDuration": total_duration,
#         "RecordingType": "continuous",
#         "iEEGReference": "n/a",
#         "ECOGChannelCount": ecognum,
#         "SEEGChannelCount": seegnum,
#         "EEGChannelCount": eegnum,
#         "EOGChannelCount": eognum,
#         "ECGChannelCount": ecgnum,
#         "EMGChannelCount": emgnum,
#         "MiscChannelCount": 0,
#         "TriggerChannelCount": 0
#         }
    
#    # with open(os.path.join(nested_dir, modlevelfolder, nested_name + '_' + f'{run_number}_ieeg.json'), 'w') as outfile:
#     with open(os.path.join(nested_dir, modlevelfolder, nested_name  + '_ieeg.json'), 'w') as outfile:
#         json.dump(ieeg_json, outfile, indent=4)




def move_mef_files(file, nested_path, nested_name, run_number):
    """ Move edf file to proper location within BIDs"""

    file_name = os.path.basename(file)
    # edf_filename = nested_name + f'_run-{run_number}.edf'
    os.rename(file, os.path.join(nested_path, file_name))
    
        

def get_run_number_from_file(file):
    """ Extract run number from edf file name"""
    # Finds the edf number and makes the run number for associated files
    last_underscore_index = file.rfind('_')
    dot_index = file.find('.', last_underscore_index)
    
    if last_underscore_index != -1 and dot_index != -1:
        return str(file[last_underscore_index + 1:dot_index]).zfill(5)
    

def create_csv(channelnames, column_names, data):

    with open(channelnames, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(column_names)
        writer.writerows(data)
    

def other_data(pipeline_folder, subject_folder, subjectid, nesteddirectory, modlevelfolder, nested_name, mri_date):
    """ Find montages if exist and place in derivative folder """
    for filename in os.listdir(pipeline_folder + '/montages'):
        folder_path = os.path.join(pipeline_folder + '/montages/', filename)
        if subjectid in filename:
            shutil.copy(pipeline_folder + '/montages/' + filename, subject_folder + '/derivative/' + subjectid + '_montage.json')
    
    """ Find annotation files and place into events.tsv"""
    for filename in os.listdir(pipeline_folder + '/annotations'):
        folder_path = os.path.join(pipeline_folder + '/annotations/', filename)
        if subjectid in filename:
            if os.path.getsize(folder_path) > 1:
               # subjannot = filename
                annotations =  pd.read_csv(pipeline_folder + '/annotations/' + filename, sep = '\t')
                annotations = annotations.iloc[:, :-4]
                annotations = annotations.rename(columns={'description': 'trial_type', 'parent': 'channel'})
                annotations.to_csv(subject_folder + '/primary/' + nesteddirectory + modlevelfolder +  '/' + nested_name + '_events.tsv', sep='\t', index=False)
                annotations_json = {
                    "trial_type": {
                        "LongName": "Event",
                        "Description": "Any annotated event by neurologist",
                    },
                    "channel": {
                        "Description": "Channel(s) associated with the event",
                        "Delimiter": ""
                    }
                }
                
                with open(subject_folder + '/primary/' + nesteddirectory + modlevelfolder + '/' + nested_name + '_events.json', "w") as outfile:
                    json.dump(annotations_json, outfile, indent=4)


# --- edited out by sz on 09/04/25 to remove EPS-related code 
# def generate_eps_string(pipeline_folder):
#     # Path to the CSV file
#     epscsv = pipeline_folder + "/epsnumber_sub.csv" # can comment out 
    
#     # Read the CSV file and get the number from the first column
#     with open(epscsv, newline='', encoding='utf-8-sig') as csvfile:
#         csvreader = csv.reader(csvfile)
#         row = next(csvreader)  
#         number = int(row[0])  
        
#     # Increment the number by 1
#     number += 1

#     # Create the string with the required formatting
#     eps_string = f"EPS{str(number).zfill(7)}"  # zfill will add leading zeros to make the string 7 digits
    


#     # Write the updated number back to the CSV file
#     print (f"About to write: {number}----")
#     print("Wrote line")
#     with open(epscsv, mode='w', newline='') as csvfile:
#         csvfile.writelines(str(number))      
        
#     return eps_string



# --- edited out by sz on 09/04/25 to remove EPS-related code 
# def replace_in_directory(subject_folder, eps_string, subject_id):
#     # Walk through the directory structure
#     for root, dirs, files in os.walk(subject_folder, topdown=False):  
#         all_items = dirs + files

#         for item in all_items:
#             old_item_path = os.path.join(root, item)

#             # Check if "sub-" is in the filename and replace the part after sub- and before the first "_"
#             new_name = item
#             if "sub-" in item:
#                 # Find the part after "sub-" and before the first "_"
#                 before_underscore = item.split("-")[1].split("_")[0]
#                 new_name = item.replace(f"sub-{before_underscore}", f"sub-{eps_string}")  
                
#             # Replace 'subjectid' with the EPS number
#             elif subject_id in item:
#                 modified_item = item.replace(subject_id, "")
#                 if len(re.findall(r'\d', modified_item)) <= 1:
#                     before_subject_id = item.split(subject_id)[0] 
#                     new_name = item.replace(before_subject_id + subject_id, eps_string)  
#                 else:
#                     pass

#             # Replace 'RID' and the next 3 characters after it with the EPS number
#             elif "RID" in item:
#                 rid_index = item.find("RID")
#                 new_name = item[:rid_index] + eps_string + item[rid_index + 6:]

#             # If the name has changed, rename the item (file or directory)
#             if new_name != item:
#                 new_item_path = os.path.join(root, new_name)

#                 # If it's a directory, rename the directory
#                 if item in dirs:
#                     os.rename(old_item_path, new_item_path)
#                     #print(f"Renamed directory {item} to {new_name}")
#                 # If it's a file, rename the file
#                 elif item in files:
#                     os.rename(old_item_path, new_item_path)
#                     #print(f"Renamed file {item} to {new_name}")



# # --- edited out by sz on 09/04/25 to remove EPS-related code 
# def update_participants_tsv(primary_dir, eps_string):
#     # Path to the participants.tsv file
#     participants_file_path = primary_dir + '/partcipants.csv'
    
#     df = pd.read_csv(participants_file_path)

#     # Replace the header "HUP Number" with "EPS Number"
#     df.columns = df.columns.str.replace('HUP Number', 'EPS Number')

#     # Replace the value under "EPS Number" column with the specified replacement value
#     df['EPS Number'] = eps_string

#     # Save the DataFrame to a TSV file (tab-separated values)
#     tsv_file_path = participants_file_path.replace('.csv', '.tsv')
#     df.to_csv(tsv_file_path, sep='\t', index=False)

#     # Delete the original CSV file
#     os.remove(participants_file_path)
    


def clean_up(new_path):
    """
    Move any file that is not 'README.txt' into the 'derivative' folder
    """
    derivative_path = os.path.join(new_path, "derivative")
    os.makedirs(derivative_path, exist_ok=True)  # Ensure derivative folder exists

    # Get all files in root which are not README.txt
    files_to_move = [
        f for f in os.listdir(new_path)
        if os.path.isfile(os.path.join(new_path, f)) and f != "README.txt"
    ]

    # Move each file to derivative
    for f in files_to_move:
        src = os.path.join(new_path, f)
        dst = os.path.join(derivative_path, f)
        shutil.move(src, dst)



def main():
    # Define arguments 
    args = parse_arguments()
    subject_folder = args.folder1
    pipeline_folder = args.folder2
    
    if subject_folder.endswith('/'):
        subject_folder=subject_folder[:-1]
        
    if pipeline_folder.endswith('/'):
        pipeline_folder=pipeline_folder[:-1]
    
    subject_id = re.sub(r"[^0-9]","", os.path.basename(subject_folder.split("_")[0]))
    subjectid = os.path.basename(subject_folder).split("_")[0]
    nested_name = "sub-" + subjectid + SES_IMPLANT_FOLDER # Implant
    
    subjectlevelfolder = 'sub-' + subjectid
    sessionlevelfolder = SES_IMPLANT_FOLDER
    
    if args.type == "ieeg":
        modlevelfolder = 'ieeg/'
    elif args.type == "scalp":
        modlevelfolder = 'eeg/'
        

    nesteddirectory = subjectlevelfolder + '/' + sessionlevelfolder + '/'
    
    # Create folder structure and BIDs files
    primary_dir, nested_dir, derivative_dir = create_folder_structure(subject_folder, subjectid)
    # create_readme_file(subject_folder)
    mri_date = create_participants_file(subject_folder, primary_dir, pipeline_folder)
    create_dataset_description(primary_dir)
    create_participants_json(primary_dir)
    os.makedirs(os.path.join(subject_folder + '/primary/' + nesteddirectory + modlevelfolder), exist_ok=True)
    
    # --- edited out by sz on 09/04/25 to remove EPS-related code 
    # eps_string = generate_eps_string(pipeline_folder)
    
    # Process .edf files
    process_edf_files(subject_folder, primary_dir, nested_dir, modlevelfolder, nested_name,pipeline_folder)
    
    """ Deal with sidecar files (imaging, montages, annotations)"""
    other_data(pipeline_folder, subject_folder, subjectid, nesteddirectory, modlevelfolder, nested_name, mri_date)
    
    
    # --- edited out by sz on 09/04/25 to remove EPS-related code 
    # replace_in_directory(subject_folder, eps_string, subject_id)
    # update_participants_tsv(primary_dir, eps_string)
    

    # --- edited out by sz on 09/04/25 to remove EPS-related code 
    #parent_dir = os.path.dirname(subject_folder) 
    #old_directory_name = os.path.basename(subject_folder)  # originally commented out 
    #new_directory_name = eps_string  
    # Create the full new path
    #new_path = os.path.join(parent_dir, new_directory_name)
    #os.rename(subject_folder, new_path)
    clean_up(subject_folder)
    
    #print(new_path)
    sys.stdout.write(subject_folder) 
    
if __name__ == '__main__':
    main()
    
    
        
