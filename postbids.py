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

# Main function to parse arguments 
def main():
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
        print(f"Error: {args.folder1} is not a valid subject directory.")
        return
    if not os.path.isdir(args.folder2):
        print(f"Error: {args.folder2} is not a valid pipeline directory.")
        return
        
    return args

if __name__ == '__main__':
    args = main()




## First replace the participants.tsv with real data
pipeline_folder = args.folder2
subject_folder = args.folder1  
filename = pipeline_folder + '/deidentified_data.csv'
subjectid = os.path.basename(subject_folder).split("_")[0]
subject_id = re.sub(r"[^0-9]", "", subjectid)
print(subject_id)


## Create folder structure 
# Get into last made directory 
os.chdir(subject_folder)
os.makedirs('Primary', exist_ok=True)
os.makedirs('Derivative', exist_ok=True)
current_folderdir = subject_folder + '/Primary/'
subjectlevelfolder = 'sub-' + subjectid
sessionlevelfolder = 'ses-01012000'

## Make README file
#f = open(current_folderdir, "w")

with open('README.txt', 'w') as f:
    f.write('References ---------- Appelhoff, S., Sanderson, M., Brooks, T., Vliet, M., Quentin, R., Holdgraf, C., Chaumon, M., Mikulan, E., Tavabi, K., Höchenberger, R., Welke, D., Brunner, C., Rockhill, A., Larson, E., Gramfort, A. and Jas, M. (2019). MNE-BIDS: Organizing electrophysiological data into the BIDS format and facilitating their analysis. Journal of Open Source Software 4: (1896).https://doi.org/10.21105/joss.01896Holdgraf, C., Appelhoff, S., Bickel, S., Bouchard, K., DAmbrosio, S., David, O., … Hermes, D. (2019). iEEG-BIDS, extending the Brain Imaging Data Structure specification to human intracranial electrophysiology. Scientific Data, 6, 102. https://doi.org/10.1038/s41597-019-0105-7')


## NEED TO ADD EEG FOR EEG INPUTS
if args.type == "ieeg":
    modlevelfolder = 'ieeg/'
elif args.type == "scalp":
    modlevelfolder = 'eeg/'

nesteddirectory = subjectlevelfolder + '/' + sessionlevelfolder +'/' + modlevelfolder
os.chdir(current_folderdir)

os.makedirs(nesteddirectory, exist_ok=True)


## Creates the participants.tsv
deiddata =  pd.read_csv(filename, encoding='latin1')
subj_deid = deiddata[deiddata.iloc[:, 0] == subject_id]
mri_date = (subj_deid['MRI Date:']).to_string(index = False)

if not subj_deid.empty:
    print(f"Found '{subject_id}' in de-identified data")
    subj_deid.to_csv((current_folderdir + "/partcipants.tsv"), index=False)
else:
    print(f"'{subject_id}' not found in the first column.")
    
#######################################################################   
#                   Creates dataset_description.json
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
# Serializing json
json_object = json.dumps(dataset_description, indent=4)
 
# Writing to sjson
with open(current_folderdir + "dataset_description.json", "w") as outfile:
    outfile.write(json_object)
    
####################################################################### 
#               Creates partcipants.json    NEEDS TO BE IMPROVED
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

json_participants = json.dumps(participantsjson, indent=4)
# Writing to sjson
with open(current_folderdir + "partcipants.json", "w") as outfile:
    outfile.write(json_participants)
    
    
    
####################################################################### 
#               Creates channel mapping and ieeg json
def find_files_by_type(folder_path, file_extension):
    
    if not os.path.isdir(folder_path):
        print(f"Error: Invalid folder path: {folder_path}")
        return []

    search_pattern = os.path.join(folder_path, "*" + file_extension)
    matching_files = glob.glob(search_pattern)
    return matching_files  

def create_csv(channelnames, column_names, data):

    with open(channelnames, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(column_names)
        writer.writerows(data)
    
file_type = ".edf"
found_files = find_files_by_type(subject_folder, file_type)

for file in found_files:
    edf_file = pyedflib.EdfReader(file)
    edffile = mne.io.read_raw_edf(file)
    column_names = ["name","type","units","low_cutoff","high_cutoff","description","sampling_frequency","status","status_description"]
    data = []
    channel_names = edffile.info['ch_names'] 
    
    # Finds the edf number and makes the run number for associated files
    last_underscore_index = file.rfind('_')
    dot_index = file.find('.', last_underscore_index)

    if last_underscore_index != -1 and dot_index != -1:
        run_number = file[last_underscore_index + 1:dot_index]
    
        
    formatted_number = str(run_number).zfill(4)
    
    nested_path = current_folderdir + nesteddirectory + subjectlevelfolder + '_' + sessionlevelfolder + '_task-rest_run-' + formatted_number

    ## NEED TO ADD FOR SCALP HERE AS WELL that makes it just eeg
    ecognum = 0
    ecgnum = 0
    emgnum = 0
    eegnum = 0
    eognum = 0
    seegnum = 0 
    for idx, channel in enumerate(edffile.info['chs']):  # Use raw channel data (not just names)
        channel_name = edffile.info['ch_names'][idx]  # Channel name (string)
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
                tyepstr = "EMG"
                emgnum += 1
                description = "Electromyography"
            elif channel['kind'] == mne.io.constants.FIFF.FIFFV_EOG_CH:
                tyepstr = "EOG"
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
        create_row = [channel_name, typestr, units, low_cutoff, high_cutoff, description, samplingfreq, "good", "n/a"]
        data.append(create_row)
   
    # Makes channel mapping varialbe
    create_csv(nested_path + '_channels.tsv', column_names, data)
    
    ieeg_json =  {
    "TaskName": "rest",
    "Manufacturer": "n/a",
    "PowerLineFrequency": "n/a",
    "SamplingFrequency": samplingfreq,
    "SoftwareFilters": "n/a",
    "RecordingDuration": edffile.times[-1],
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
    
    json_ieeg = json.dumps(ieeg_json, indent=4)
    # Writing to sjson
    with open(nested_path+ "_ieeg.json", "w") as outfile:
        outfile.write(json_ieeg)
        
    ###################################################################
     #                Moves the edf files to the appropriate directory 
     
    indv_edf_filename = os.path.basename(file).split("/")[-1]
    os.rename(file, current_folderdir + nesteddirectory + '/' + indv_edf_filename)


    edf_file.close()
    del edf_file
    edffile.close()
    del edffile
#######################################################################
#                Creates events.tsv and .json

for filename in os.listdir(pipeline_folder + '/annotations'):
    folder_path = os.path.join(pipeline_folder + '/annotations/', filename)
    if subjectid in filename:
        subjannot = filename
        annotations =  pd.read_csv(pipeline_folder + '/annotations/' + filename, sep = '\t')
        annotations = annotations.iloc[:, :-4]
        annotations = annotations.rename(columns={'description': 'trial_type', 'parent': 'channel'})
        annotations.to_csv(current_folderdir + '/' + nesteddirectory + '/' + subjectlevelfolder + '_' + sessionlevelfolder + '_events.tsv', sep='\t', index=False)
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
        
        json_annotations = json.dumps(annotations_json, indent=4)
        # Writing to sjson
        with open(current_folderdir + '/' + nesteddirectory + '/' + subjectlevelfolder + '_' + sessionlevelfolder + '_events.json', "w") as outfile:
            outfile.write(json_annotations)


    
 ####################################################################### 
 #               Finds if imaging exists and properly moves it
imaging_directory_found = False
for filename in os.listdir(subject_folder):
    folder_path = os.path.join(subject_folder, filename)
    if "imag" in filename and os.path.isdir(folder_path):
        print(filename)
        imaging_directory_found = True
        imaging_type = ".nii"
        imaging_files = find_files_by_type(subject_folder + '/' + filename, imaging_type)
        for imaging in imaging_files:
            if "ct" in imaging.lower():
                os.chdir(current_folderdir + subjectlevelfolder + '/' + sessionlevelfolder)
                os.makedirs('ct', exist_ok=True)
                ct_path = current_folderdir + subjectlevelfolder + '/' + sessionlevelfolder + '/ct/' + subjectlevelfolder + '-' + sessionlevelfolder + '_run-01_ct.nii'
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
                with open(current_folderdir + subjectlevelfolder + '/' + sessionlevelfolder + '/ct/' + subjectlevelfolder + '-' + sessionlevelfolder + "_run-01_ct.json", "w") as outfile:
                    outfile.write(json_ct)
            elif any(x in imaging.lower() for x in ["t1", "t2", "flair"]): 
                datemriobj = datetime.strptime(mri_date, "%m/%d/%y")
                formatted_date = datemriobj.strftime("%m%d%Y")
                
                os.makedirs(os.path.join(current_folderdir, subjectlevelfolder, 'ses-' + formatted_date, 'anat'), exist_ok=True)

                rootmri = current_folderdir + subjectlevelfolder + '/ses-' + formatted_date + '/anat/' + subjectlevelfolder + '_ses-' + formatted_date
                if "t2" in imaging.lower():
                    mri_path = rootmri + '_run-01_T2.nii'
                    shutil.copy(imaging, mri_path)
                    jsonpath = rootmri + '_run-01_T2.json'
                else: 
                    mri_path = rootmri + '_run-01_T1w.nii'
                    shutil.copy(imaging, mri_path)
                    jsonpath = rootmri + '_run-01_T1w.json'
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
                    

             

if not imaging_directory_found: 
    print("No imaging directory found")
    
    
 ####################################################################### 
 #               Find montage and move into Derivative folder 
        
for filename in os.listdir(pipeline_folder + '/montages'):
    folder_path = os.path.join(pipeline_folder + '/montages/', filename)
    if subjectid in filename:
        shutil.copy(pipeline_folder + '/montages/' + filename, subject_folder + '/Derivative/' + filename)
        
 
      

        
