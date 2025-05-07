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

def parse_arguments():
    """ Parse command line arguments"""
    # Set up argparse to handle command line arguments
    parser = argparse.ArgumentParser(description="Process input folders with a flag for either iEEG or scalp data.")
    
    # Add arguments for the two folders and the flag
    parser.add_argument('folder1', type=str, help="Path to the subject folder folder")
    parser.add_argument('folder2', type=str, help="Path to the pipeline creation folder")
    parser.add_argument('type', type=str, choices=['ieeg', 'scalp'], help="Flag indicating data type: 'ieeg' or 'scalp'")

    # Parse the command line arguments
    args = parser.parse_args()

    # Validate if the provided folders exist
    if not os.path.isdir(args.folder1):
        #print(f"Error: {args.folder1} is not a valid subject directory.")
        return
    if not os.path.isdir(args.folder2):
        #print(f"Error: {args.folder2} is not a valid pipeline directory.")
        return
        
    return args

def create_folder_structure(subject_folder, subjectid):
    """ Creates primary and derivative folder structures"""
    os.makedirs(os.path.join(subject_folder, 'Primary'), exist_ok=True)
    os.makedirs(os.path.join(subject_folder, 'Derivative'), exist_ok=True)
    
    primary_dir = os.path.join(subject_folder, 'Primary')
    derivative_dir = os.path.join(subject_folder, 'Derivative')
    ## Nested directory is the primary directory than subject folder than session folder 
    nested_dir = os.path.join(primary_dir, f'sub-{subjectid}', 'ses-01012000')
    
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
    
    

def process_edf_files(subject_folder, primary_dir, nested_dir, args, nested_name, eps_string):
    """ Creates channels.tsv file for all data """
    
    ## NEED TO ADD EEG FOR EEG INPUTS
    if args.type == "ieeg":
        modlevelfolder = 'ieeg/'
    elif args.type == "scalp":
        modlevelfolder = 'eeg/'


    column_names = ["name","type","units","low_cutoff","high_cutoff","description","sampling_frequency","status","status_description"]
    data = []
    
        
    """ Process edf files and generate all sidecar files """
    found_files = find_files_by_type(subject_folder +'/', '.edf')
    total_duration = 0
    
    logging.getLogger('pyedflib').setLevel(logging.CRITICAL)
    mne.set_log_level('CRITICAL')
    

    edf_file = pyedflib.EdfReader(found_files[0])
    edffile = mne.io.read_raw_edf(found_files[0])
        
    ecognum = 0
    ecgnum = 0
    emgnum = 0
    eegnum = 0
    eognum = 0
    seegnum = 0 
    
    for idx, channel in enumerate(edffile.info['chs']):  # Use raw channel data (not just names)
        channel_name = edffile.info['ch_names'][idx]  # Channel name (string)
        """ Find the type and description for each channel """
        if args.type == 'scalp':
            typestr = "EEG"
            eegnum += 1
            description = "Electroencephalography"
        elif args.type == 'ieeg':
            if "grid" in channel_name.lower() or channel['kind'] == mne.io.constants.FIFF.FIFFV_EOG_CH:
                typestr = "ECOG"
                ecognum += 1
                description = "Electrocorticography"
            elif channel['kind'] == mne.io.constants.FIFF.FIFFV_ECG_CH:
                typestr = "ECG"
                ecgnum += 1
                description = "Electrocardiography"
            elif channel['kind'] == mne.io.constants.FIFF.FIFFV_EMG_CH:
                typestr = "EMG"
                emgnum += 1
                description = "Electromyography"
            elif channel['kind'] == mne.io.constants.FIFF.FIFFV_EOG_CH:
                typestr = "EOG"
                eognum += 1
                description = "Electrooculography"
            elif channel['kind'] == mne.io.constants.FIFF.FIFFV_EEG_CH:
                typestr = "SEEG"
                seegnum += 1
                description = "Stereoelectroencephalography"
        
        units = edf_file.getPhysicalDimension(1)
        low_cutoff = edffile.info.get('lowpass')
        high_cutoff = edffile.info.get('highpass')
        samplingfreq = edffile.info.get('sfreq')
        ## Add if loop if multiple folders for subject are here 
            ## add stuff here for channel status if it was removed 
        data.append([channel_name, typestr, units, low_cutoff, high_cutoff, description, samplingfreq, "good", "n/a"])
        
        file_path = os.path.join(nested_dir, modlevelfolder, nested_name + '_channels.tsv')
        with open(file_path, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(column_names)
            writer.writerows(data)
            
    edf_file.close()
    del edf_file
    edffile.close()
    del edffile
            
    for file in found_files:
        
        with open(file, 'rb+') as f:
            new_bytes = eps_string.encode('utf-8') 
            file_data = f.read()
            
            modified_data = file_data[:8] + new_bytes + file_data[8 + 80:]

            f.seek(0)
            f.write(modified_data)
            
            
        edf_file = pyedflib.EdfReader(file)
        edffile = mne.io.read_raw_edf(file)
        run_number =get_run_number_from_file(file)
        # Find duration per edf file and add to overall duration variable 
        total_duration += edffile.times[-1]
        
        edffile.info['patient_id'] = eps_string

        edffile.save(file, overwrite=True)
        
        nested_path = nested_dir + '/' + modlevelfolder +'/'
        
        # Move edf files
        move_edf_file(file, nested_path + '/', nested_name, run_number)
        
        edf_file.close()
        del edf_file
        edffile.close()
        del edffile
            
        
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



def move_edf_file(file, nested_path, nested_name, run_number):
    """ Move edf file to proper location within BIDs"""
    #edf_filename = os.path.basenmae(file)
    edf_filename = nested_name + f'_run-{run_number}.edf'
    os.rename(file, os.path.join(nested_path, edf_filename))
    
        

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
            shutil.copy(pipeline_folder + '/montages/' + filename, subject_folder + '/Derivative/' + subjectid + 'montage.json')
    
    """ Find annotation files and place into events.tsv"""
    for filename in os.listdir(pipeline_folder + '/annotations'):
        folder_path = os.path.join(pipeline_folder + '/annotations/', filename)
        if subjectid in filename:
            if os.path.getsize(folder_path) > 1:
               # subjannot = filename
                annotations =  pd.read_csv(pipeline_folder + '/annotations/' + filename, sep = '\t')
                annotations = annotations.iloc[:, :-4]
                annotations = annotations.rename(columns={'description': 'trial_type', 'parent': 'channel'})
                annotations.to_csv(subject_folder + '/Primary/' + nesteddirectory + modlevelfolder +  '/' + nested_name + '_events.tsv', sep='\t', index=False)
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
                
                with open(subject_folder + '/Primary/' + nesteddirectory + modlevelfolder + '/' + nested_name + '_events.json', "w") as outfile:
                    json.dump(annotations_json, outfile, indent=4)


        
     ####################################################################### 
     #               Finds if imaging exists and properly moves it
    imaging_directory_found = False
    run_number_ct = 1
    # Check if objects folder exists here 
    object_dir = subject_folder + '/objects'
    if os.path.isdir(object_dir):
        for filename in os.listdir(object_dir):
            folder_path = os.path.join(object_dir, filename)
            # change the name when unzipped so annoying
            if "imag" in filename and os.path.isdir(folder_path):
                #print(filename)
                imaging_directory_found = True
                imaging_type = ".nii"
                imaging_files = find_files_by_type(object_dir + '/' + filename, imaging_type)
                for imaging in imaging_files:
                    if "ct" in imaging.lower():
                        os.chdir(subject_folder + '/Primary/' + nesteddirectory)
                        if run_number_ct == 1:
                            os.makedirs('ct', exist_ok=True)
                        ct_path = subject_folder + '/Primary/' + nesteddirectory + 'ct/' + nested_name + f'_run-{run_number_ct:02d}_ct.nii'
                        shutil.copy(imaging, ct_path)
                        ct_json = {
                        "Modality": "CT",  
                        "ImagingFrequency": 0,
                        "Manufacturer": "",
                        "ManufacturersModelName": "",  
                        "InstitutionName": "", 
                        "InstitutionAddress": "", 
                        "DeviceSerialNumber": "",  
                        "StationName": "",  
                        "BodyPartExamined": "",
                        "PatientPosition": "",  
                        "SoftwareVersions": "",  
                        "SeriesDescription": "",  
                        "ProtocolName": "", 
                        "ImageType": "",  
                        "SeriesNumber": "",  
                        "AcquisitionTime": "",  
                        "AcquisitionNumber": "",  
                        "ImageComments": "",  
                        "ConvolutionKernel": "",  
                        "ExposureTime": "", 
                        "XRayTubeCurrent": "",  
                        "XRayExposure": "", 
                        "ImageOrientationPatientDICOM": "",  
                        "ConversionSoftware": "",  
                        "ConversionSoftwareVersion": ""
                    }
                        json_ct = json.dumps(ct_json, indent=4)
                        # Writing to json
                        with open(subject_folder + '/Primary/' + nesteddirectory + '/ct/' + nested_name + f'_run-{run_number_ct:02d}_ct.json', "w") as outfile:
                            outfile.write(json_ct)
                        run_number_ct += 1
                        
                    if any(x in imaging.lower() for x in ["t1", "t2", "flair","mprage"]):
                        #print("Made it inside imaging loop")
                        run_number_t2 = 1 
                        run_number_t1 = 1  
                        date_pattern = r'(\d{8})'
                        
                        match = re.search(date_pattern, imaging)
                        #If date is in string do this
                        if match:
                            date_str = match.group(1)
                            date_obj = datetime.strptime(date_str, "%Y%m%d")
                            formatted_date = date_obj.strftime("%m%d%Y")
                            
                            folder_path = os.path.join(subject_folder, 'Primary', f'sub-{subjectid}', f'ses-{formatted_date}', 'anat')

                            # Check if the folder exists
                            if not os.path.exists(folder_path):
                                os.makedirs(folder_path, exist_ok=True)
                            
                            rootmri = subject_folder  + '/Primary/sub-' + subjectid + '/ses-' + formatted_date + '/anat/sub-' + subjectid + '_ses-' + formatted_date
                    
                            
                        # If no date in string search the participants tsv to find date
                        else:                    
                            if run_number_t2 == 1 and run_number_t2 == 1:
                        
                                datemriobj = datetime.strptime(mri_date, "%m/%d/%y")
                                formatted_date = datemriobj.strftime("%m%d%Y")
                            
                                os.makedirs(subject_folder + '/Primary/sub-' + subjectid + '/ses-' + formatted_date + '/anat', exist_ok=True)
                                rootmri = subject_folder  + '/Primary/sub-' + subjectid + '/ses-' + formatted_date + '/anat/sub-' + subjectid + '_ses-' + formatted_date
                        
                        if "t2" in imaging.lower():
                            mri_path = rootmri + f'_run-{run_number_t2:02d}_T2.nii'
                            shutil.copy(imaging, mri_path)
                            jsonpath = rootmri + f'_run-{run_number_t2:02d}_T2.json'
                            run_number_t2 += 1  
                        else: 
                            mri_path = rootmri + f'_run-{run_number_t1:02d}_T1w.nii'
                            shutil.copy(imaging, mri_path)
                            jsonpath = rootmri + f'_run-{run_number_t1:02d}_T1w.json'
                            run_number_t1 += 1
                        mri_json = {
                        "Modality": "MR",
                        "MagneticFieldStrength": "",
                        "ImagingFrequency": "",
                        "Manufacturer": "",
                        "ManufacturersModelName": "",
                        "InstitutionName": "",
                        "InstitutionalDepartmentName": "",
                        "InstitutionAddress": "",
                        "DeviceSerialNumber": "",
                        "StationName": "",
                        "BodyPartExamined": "",
                        "PatientPosition": "",
                        "ProcedureStepDescription": "",
                        "SoftwareVersions": "",
                        "MRAcquisitionType": "",
                        "SeriesDescription": "",
                        "ProtocolName": "",
                        "ScanningSequence": "",
                        "SequenceVariant": "",
                        "ScanOptions": "",
                        "SequenceName": "",
                        "ImageType": [""
                        ],
                        "NonlinearGradientCorrection": "",
                        "SeriesNumber": "",
                        "AcquisitionTime": "",
                        "AcquisitionNumber": "",
                        "SliceThickness": "",
                        "SAR": "",
                        "EchoTime": "",
                        "RepetitionTime": "",
                        "InversionTime": "",
                        "FlipAngle": "",
                        "PartialFourier": "",
                        "BaseResolution": "",
                        "ShimSetting": [""
                        ],
                        "TxRefAmp": "",
                        "PhaseResolution": "",
                        "ReceiveCoilName": "",
                        "CoilString": "",
                        "PulseSequenceDetails": "",
                        "CoilCombinationMethod": "",
                        "MatrixCoilMode": "",
                        "PercentPhaseFOV": "",
                        "PercentSampling": "",
                        "PhaseEncodingSteps": "",
                        "AcquisitionMatrixPE": "",
                        "ReconMatrixPE": "",
                        "PixelBandwidth": "",
                        "DwellTime": "",
                        "ImageOrientationPatientDICOM": [""
                        ],
                        "ImageOrientationText": "",
                        "InPlanePhaseEncodingDirectionDICOM": "",
                        "ConversionSoftware": "",
                        "ConversionSoftwareVersion": ""
                    }
                        
                        json_mri = json.dumps(mri_json, indent=4)
                        # Writing to json, UPDATE THE SESSION LEVEL FOLDER !!!!
                        with open(jsonpath, "w") as outfile:
                            outfile.write(json_mri)

   # if not imaging_directory_found: 
        #print("No imaging directory found")

def generate_eps_string(pipeline_folder):
    # Path to the CSV file
    epscsv = pipeline_folder + "/epsnumber.csv"
    
    # Read the CSV file and get the number from the first column
    with open(epscsv, newline='', encoding='utf-8-sig') as csvfile:
        csvreader = csv.reader(csvfile)
        row = next(csvreader)  
        number = int(row[0])  
        
    # Increment the number by 1
    number += 1

    # Create the string with the required formatting
    eps_string = f"EPS{str(number).zfill(7)}"  # zfill will add leading zeros to make the string 7 digits
    
    new_num = str(number)

    # Write the updated number back to the CSV file
    with open(epscsv, mode='w', newline='') as csvfile:
        csvwriter = csv.writer(csvfile)
        csvwriter.writerows(new_num)
        
        
    return eps_string


def replace_in_directory(subject_folder, eps_string, subject_id):
    # Walk through the directory structure
    for root, dirs, files in os.walk(subject_folder, topdown=False):  
        all_items = dirs + files

        for item in all_items:
            old_item_path = os.path.join(root, item)

            # Check if "sub-" is in the filename and replace the part after sub- and before the first "_"
            new_name = item
            if "sub-" in item:
                # Find the part after "sub-" and before the first "_"
                before_underscore = item.split("-")[1].split("_")[0]
                new_name = item.replace(f"sub-{before_underscore}", f"sub-{eps_string}")  
                
            # Replace 'subjectid' with the EPS number
            elif subject_id in item:
                modified_item = item.replace(subject_id, "")
                if len(re.findall(r'\d', modified_item)) <= 1:
                    before_subject_id = item.split(subject_id)[0] 
                    new_name = item.replace(before_subject_id + subject_id, eps_string)  
                else:
                    pass

            # Replace 'RID' and the next 3 characters after it with the EPS number
            elif "RID" in item:
                rid_index = item.find("RID")
                new_name = item[:rid_index] + eps_string + item[rid_index + 6:]

            # If the name has changed, rename the item (file or directory)
            if new_name != item:
                new_item_path = os.path.join(root, new_name)

                # If it's a directory, rename the directory
                if item in dirs:
                    os.rename(old_item_path, new_item_path)
                    #print(f"Renamed directory {item} to {new_name}")
                # If it's a file, rename the file
                elif item in files:
                    os.rename(old_item_path, new_item_path)
                    #print(f"Renamed file {item} to {new_name}")

def update_participants_tsv(primary_dir, eps_string):
    # Path to the participants.tsv file
    participants_file_path = primary_dir + '/partcipants.csv'
    
    df = pd.read_csv(participants_file_path)

    # Replace the header "HUP Number" with "EPS Number"
    df.columns = df.columns.str.replace('HUP Number', 'EPS Number')

    # Replace the value under "EPS Number" column with the specified replacement value
    df['EPS Number'] = eps_string

    # Save the DataFrame to a TSV file (tab-separated values)
    tsv_file_path = participants_file_path.replace('.csv', '.tsv')
    df.to_csv(tsv_file_path, sep='\t', index=False)

    # Delete the original CSV file
    os.remove(participants_file_path)
    
     
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
    nested_name = "sub-" + subjectid + '_ses-01012000'
    
    subjectlevelfolder = 'sub-' + subjectid
    sessionlevelfolder = 'ses-01012000'
    
    if args.type == "ieeg":
        modlevelfolder = 'ieeg/'
    elif args.type == "scalp":
        modlevelfolder = 'eeg/'
        

    nesteddirectory = subjectlevelfolder + '/' + sessionlevelfolder + '/'
    
    # Create folder structure and BIDs files
    primary_dir, nested_dir, derivative_dir = create_folder_structure(subject_folder, subjectid)
    create_readme_file(subject_folder)
    mri_date = create_participants_file(subject_folder, primary_dir, pipeline_folder)
    create_dataset_description(primary_dir)
    create_participants_json(primary_dir)
    os.makedirs(os.path.join(subject_folder + '/Primary/' + nesteddirectory + modlevelfolder), exist_ok=True)
    
    eps_string = generate_eps_string(pipeline_folder)
    
    # Process .edf files
    process_edf_files(subject_folder, primary_dir, nested_dir, args, nested_name, eps_string)
    
    """ Deal with sidecar files (imaging, montages, annotations)"""
    other_data(pipeline_folder, subject_folder, subjectid, nesteddirectory, modlevelfolder, nested_name, mri_date)
    
    
    
    replace_in_directory(subject_folder, eps_string, subject_id)
    
    update_participants_tsv(primary_dir, eps_string)
    
    parent_dir = os.path.dirname(subject_folder) 
    #old_directory_name = os.path.basename(subject_folder)  
    new_directory_name = eps_string  

    # Create the full new path
    new_path = os.path.join(parent_dir, new_directory_name)
    os.rename(subject_folder, new_path)
    
    #print(new_path)
    sys.stdout.write(new_path) 
    
if __name__ == '__main__':
    main()
    
    
        
