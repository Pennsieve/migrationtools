from DatsetDescriptionSidecar import DatasetDescriptionSidecar
from SessionsSidecar import SessionSidecar
from ParticipantsSidecar import ParticipantsSidecar
from ParticipantsSidecarTSV import ParticipantsSideCarTSV
from IEEGSidecar import IeegSidecar
from ChannelsSidecar import ChannelsSidecar
from CoordSystemSidecar import CoordSystemSidecar
from ElectrodesSidecar import ElectrodesSidecar
from EEGSidecar import EEGSidecar
from EventsSidecar import EventsSidecar
from helpers import *
from pathlib import Path
from typing import Dict, Any

MASTER_MIGRATION_METADATA = "input/mastermigration_metadata.csv"
MASTER_SUBJECT_METADATA = "input/mastersubject_metadata.csv"
PREFIX = "PennEPI"

data_map = {}

def createEventsSidecar(name,data_map):
    events_data = [
            {
                "onset": 0.0,
                "duration": 1.2,
                "trial_type": "visual",
                "response_time": 0.85,
                "HED": "Sensory-event, Visual, Bright flash",
                "stim_file": "stimulus1.jpg",
                "channel": "EOG",
                "Description": "Visual flash stimulus",
                "Parent": "block_01",
                "Annotated": "true",
                "Annotator": "nishant",
                "Type": "stimulus",
                "Layer": "primary",
            },
            {
                "onset": 2.0,
                "duration": 1.5,
                "trial_type": "auditory",
                "response_time": 1.0,
                "stim_file": "tone.wav",
                "Type": "stimulus",
            },
        ]

    sidecar = EventsSidecar()
    sidecar.save(data=events_data, output_dir=f"output/{name}/bids")

def createEEGSidecar(name,data_map):
    eeg_fields = {
            "TaskName": "RestingState",
            "EEGReference": "Cz",
            "SamplingFrequency": 500,
            "PowerLineFrequency": 60,
            "SoftwareFilters": "n/a",
            "RecordingType": "continuous",
            "Manufacturer": "BrainProducts",
            "ManufacturersModelName": "actiCHamp",
            "SoftwareVersions": "v2.1.0",
            "EEGChannelCount": 64,
            "EEGPlacementScheme": "10-20 system",
            "SubjectArtefactDescription": "Minor muscle artefacts noted.",
        }

    eeg_sidecar = EEGSidecar(eeg_fields)
    eeg_sidecar.save(output_dir=f"output/{name}/bids", json_indent=4)

def createElectrodesSidecar(name):
    # source:  Files/derivatives/ieeg_recon/module4/electrodes2ROI_mni.csv

    electrodes_payload = []
    electrode_data = load_data(f"electrode_data_{name}")
    electrode_text = load_data(f"electrode_txt_data_{name}")
    

    if electrode_data != None:
        for data in electrode_data:
            label = data.get("labels","")
            # FROM: Files/derivatives/voxtool_ct/electodes.txt. use last two columns, reversed. ie: 10 1 -> 1x10
            raw_dimensions = electrode_text[label]["group"]
            dimensions = raw_dimensions.split(" ")
            dimension = f"{dimensions[1]}x{dimensions[0]}"

            electrodes_payload.append({
                "name": label,
                "x": data.get("mm_x",""),
                "y": data.get("mm_y",""),
                "z": data.get("mm_z",""),
                "size": ELECTRODES_SIZE,
                "manufacturer": ELECTRODES_MANUFACTURER,
                "group": name[:2].upper(),
                "hemisphere": name[0].upper(),
                "type": ELECTRODES_GROUP,
                "dimension": dimension,
                "roi": data.get("roi",""),
            })
        sidecar = ElectrodesSidecar()
        sidecar.save(data=electrodes_payload, output_dir=f"output/{name}/bids")

def createCoordsSidecar(name):
    coord_fields = {
            "IntendedFor": "bids::derivatives/freesurfer/mri/T1.nii.gz",
            "iEEGCoordinateSystem": "MNI152NLin6ASym",
            "iEEGCoordinateUnits": "mm",
            "iEEGCoordinateSystemDescription": "Transformation of electrodes to MNI152NLin2009cAsym standard space",
            "iEEGCoordinateProcessingDescription": "derivatives/ieeg_recon/dataset_description.json: PipelineSteps, Name: Module4_MNI152_Transformation",
            "iEEGCoordinateProcessingReference": "Lucas A, Scheid BH, Pattnaik AR, Gallagher R, Mojena M, Tranquille A, Prager B, Gleichgerrcht E, Gong R, Litt B, Davis KA, Das S, Stein JM, Sinha N. iEEG-recon: A fast and scalable pipeline for accurate reconstruction of intracranial electrodes and implantable devices. Epilepsia. 2024 Mar;65(3):817-829. doi: 10.1111/epi.17863. Epub 2024 Jan 10. PMID: 38148517; PMCID: PMC10948311.",
        }

    sidecar = CoordSystemSidecar(coord_fields,filename=f"PREFIX_space-{coord_fields["iEEGCoordinateSystem"]}_coordsystem.json")
    sidecar.save(output_dir=f"output/{name}/bids", json_indent=4)

def createChannelsDataSidecar(name,data_map):
    channels_data = [
            {
                "name": "EKG1",
                "type": "ECG",
                "units": "uV",
                "low_cutoff": "n/a",
                "high_cutoff": "n/a",
                "reference": "unknown",
                "ground": "unknown",
                "group": "n/a",
                "sampling_frequency": "n/a",
                "notch": "n/a",
            },
            {
                "name": "LA01",
                "type": "SEEG",
                "units": "uV",
                "low_cutoff": "n/a",
                "high_cutoff": 0.01,
                "reference": "LE10",
                "ground": "RF6",
                "group": "LA",
                "sampling_frequency": 256,
                "notch": "n/a",
            },
            {
                "name": "LA02",
                "type": "SEEG",
                "units": "uV",
                "low_cutoff": "n/a",
                "high_cutoff": 0.01,
                "reference": "LE10",
                "ground": "RF6",
                "group": "LA",
                "sampling_frequency": 256,
                "notch": "n/a",
            },
        ]

    sidecar = ChannelsSidecar()
    sidecar.save(data=channels_data, output_dir=f"output/{name}/bids")

def createIEEGDataSidecar(name,key,data_map):

    def save_ieeg_sidecar(name, sampling_frquency, recording_duration, channel_counts, data,path):

        ieeg_data = {
            "TaskName": TASK_NAME, # ok
            "TaskDescription": IEEG_TASK_DESCRIPTION,# ok
            "InstitutionName": INSTITUTION_NAME, # ok
            "Manufacturer": data.get("Manufacturer","n/a"), # ok
            "ManufacturersModelName": data.get("ManufacturersModelName","n/a"),
            "ElectrodeManufacturer":data.get("ElectrodeManufacturer","n/a"),
            "iEEGReference": data.get("iEEGReference","n/a"), # ok
            "iEEGGround": data.get("iEEGGround","n/a"), # ok
            "SamplingFrequency": sampling_frquency, #ok
            "PowerLineFrequency": POWER_LINE_FREQUENCY, # ok
            "SoftwareFilters": SOFTWARE_FILTERS,  # ok
            "ECOGChannelCount": channel_counts["ECOGChannelCount"],  # ok
            "SEEGChannelCount": channel_counts["SEEGChannelCount"],  # ok
            "EEGChannelCount": channel_counts["EEGChannelCount"],  # ok
            "EOGChannelCount": channel_counts["EOGChannelCount"],  # ok
            "ECGChannelCount": channel_counts["ECGChannelCount"],  # ok
            "EMGChannelCount": channel_counts["EMGChannelCount"],  # ok
            "MiscChannelCount": channel_counts["MiscChannelCount"],  # ok
            "TriggerChannelCount": channel_counts["TriggerChannelCount"],  # TODO: COnfirm
            "RecordingDuration": recording_duration, # ok
            "RecordingType": RECORDING_TYPE, # ok
            "HardwareFilters":{
                "Hardware bandwidth filter":{
                    "min (Hz)": data.get("hardwarebandwith_in","n/a"),
                    "max (Hz)": data.get("hardwarebandwith_max","n/a"),
                }
            }
        }

        sidecar = IeegSidecar(ieeg_data, filename=f"sub-{key}-postimplant_ieeg.json")
        sidecar.save(output_dir=path)

    def get_sampling_frequency(path):
        # Get Sampling Frequency and Recording duration
        try:
            with open(path) as f:
                reader = csv.DictReader(f, delimiter="\t")
                row = next(reader)
                return row.get("sampling_frequency", "n/a")
        except FileNotFoundError:
            return "n/a"
        
    def get_recording_duration(key, sub_key=None):
        payload = load_data("payload")
        try:
            if sub_key == None:
                return payload[key]["duration"]
            else:
                return payload[key][sub_key]["duration"]
        except KeyError as e:
            return -1
        
    def get_channel_counts(path):
        counts = {
            "ECOGChannelCount": 0,
            "SEEGChannelCount": 0,
            "EEGChannelCount": 0,
            "EOGChannelCount": 0,
            "ECGChannelCount": 0,
            "EMGChannelCount": 0,
            "MiscChannelCount": 0,
            "TriggerChannelCount": 0,
        }
        try:
            with open(path) as f:
                reader = csv.DictReader(f,delimiter="\t")
                for line in reader:
                    if line["type"].lower().strip() == "ecog":
                        counts["ECOGChannelCount"] +=1
                    elif line["type"].lower().strip() == "seeg":
                        counts["SEEGChannelCount"] +=1
                    elif line["type"].lower().strip() == "eeg":
                        counts["EEGChannelCount"] +=1
                    elif line["type"].lower().strip() == "eog":
                        counts["EOGChannelCount"] +=1
                    elif line["type"].lower().strip() == "ecg":
                        counts["ECGChannelCount"] +=1
                    elif line["type"].lower().strip() == "emg":
                        counts["EMGChannelCount"] +=1
                    elif line["type"].lower().strip() == "trigger": # TODO: Confirm
                        counts["TriggerChannelCount"] +=1
                    else:
                        counts["MiscChannelCount"] +=1
        except FileNotFoundError:
            return counts

        return counts
    


    # detect if this EPS has subdatasets (D01, D02, ...)
    if any(k.startswith("D0") for k in data_map.get(key).keys()):
        for sub_key, sub_data in data_map.get(key).items():
            if not sub_key.startswith("D0"):
                continue

            path = f"{OUTPUT_DIR}/{name}/bids/{sub_key}"
            channels_path = os.path.join(OUTPUT_DIR, name,"bids",sub_key, "channels.tsv")
            sampling_frquency = get_sampling_frequency(channels_path)
            recording_duration = get_recording_duration(key,sub_key)
            channel_counts = get_channel_counts(channels_path)

            save_ieeg_sidecar(name, sampling_frquency, recording_duration, channel_counts, data_map.get(key),path)
    else:
        path = f"{OUTPUT_DIR}/{name}/bids"
        channels_path = os.path.join(OUTPUT_DIR, name, "bids", "channels.tsv")
        sampling_frquency = get_sampling_frequency(channels_path)
        recording_duration = get_recording_duration(key)
        channel_counts = get_channel_counts(channels_path)
        save_ieeg_sidecar(name, sampling_frquency, recording_duration, channel_counts, data_map.get(key),path)   

def createSessionsDataSidecar(name,key,data_map):
    
    subject = data_map.get(key, {})
    subject_age_session_postimplant = subject.get("age_iEEGimplant","n/a")
    subject_age_session_postsurgery = subject.get("age_procedure","n/a")
    subject_age_session_postsurgery_preimplant_anat = subject.get("age_t3scan","n/a")
    subject_age_session_postsurgery_preimplant_eeg = subject.get("age_preeeg","n/a")

    sessions_data = [
            {
                "session_id": "ses-postimplant",
                "session_description": "intracranial evaluation",
                "subject_age_session": subject_age_session_postimplant,
            },
            {
                "session_id": "ses-postsurgery",
                "session_description": "post surgical treatment follow up, no sooner than 15months",
                "subject_age_session": subject_age_session_postsurgery,
            },
            {
                "session_id": "ses-preimplant/anat",
                "session_description": "mri prior to intracranial evaluation",
                "subject_age_session": subject_age_session_postsurgery_preimplant_anat,
            },
            # {
            #     "session_id": "ses-preimplant/eeg",
            #     "session_description": "eeg prior to intracranial evaluation",
            #     "subject_age_session": subject_age_session_postsurgery_preimplant_eeg,
            # },
        ]
    session_sidecar = SessionSidecar(filename=f"sub-{key}_sessions.tsv")

    session_sidecar.save(data=sessions_data, output_dir=f"output/{name}/bids")

def createParticipantsTSVSidecar(name,key,data_map):
    try:
        sex = data_map[key].get("sex","n/a")
    except KeyError as e:
        sex = "n/a"
    pariticpant_data = [
            {
                "participant_id": f"sub-{name}",
                "species": SPECIES,
                "population": POPULATION,
                "sex": sex, 
                "MRI_lesion":"",
                'MRI_lesionDetails':"",
                "ieeg_isFocal": "",
                "intervention_type": "",
                "intervention_location":"",
                "seizure_Engel12m":"",
                "seizure_Engel24m":"",
                "fiveSenseScore":"",
            },

        ]
    pariticpant_sidecar = SessionSidecar()
    pariticpant_sidecar.save(data=pariticpant_data, output_dir=f"output/{name}/bids")

def createParticipantsSidecar(name):
    participants_sidecar = ParticipantsSidecar({
        "participant_id": {
            "Description": "Unique participant identifier"
        },
        "species": {
            "Description": "Species of the participant",
            "Levels": {
                "homo sapiens": "Human"
            }
        },
        "population": {
            "Description": "Adult or pediatric population classification",
            "Levels": {
                "adult": "adult",
                "pediatric": "pediatric"
            }
        },
        "sex": {
            "Description": "Biological sex of the subject, collected from health record",
            "Levels": {
                "Female": "Female",
                "Male": "Male"
            }
        },
        "MRI_lesion": {
            "Description": "Preimplant MRI lesion status",
            "Levels": {
                "lesional": "lesional",
                "nonlesional": "nonlesional",
                "n/a": "not available"
            }
        },
        "MRI_lesionType": {
            "Description": "Type of MRI lesion",
            "Levels": {
                "Encephalocele": "Encephalocele",
                "FCD": "Focal Cortical Dysplasia",
                "MTS": "Medial Temporal Sclerosis",
                "Multiple": "see MRI_lesionDetails for description",
                "Prior surgery": "prior resection",
                "PVNH": "periventricular nodular heterotopia",
                "Tubers": "Tubers",
                "n/a": "nonlesional",
                "Other": "see MRI_lesionDetails for description"
            }
        },
        "MRI_lesionDetails": {
            "Description": "Type of MRI lesion, specified",
            "Units": "string"
        },
        "ieeg_isFocal": {
            "Description": "Postimplant determination of seizure onset focality",
            "Levels": {
                "focal": "focal",
                "nonfocal": "nonfocal"
            }
        },
        "intervention_type": {
            "Description": "Postimplant intervention, associated data in postsurgery session if applicable",
            "Levels": {
            "ablation": "laser ablation",
            "DBS": "Deep brain stimulation device",
            "medication": "medication management, no surgical intervention post iEEG implant",
            "resection": "resection",
            "RNS": "Responsive neurostimulation (NeuroPace RNS System)",
            "VNS": "Vagal nerve stimulator device"
            }
        },
        "intervention_side": {
            "Description": "Hemisphere of surgical intervention",
            "Levels": {
                "Bilateral": "Bilateral",
                "Left": "Left",
                "Right": "Right",
                "n/a": "no surgical intervention"
            }
        },
        "intervention_location": {
            "Description": "Brain region of surgical intervention",
            "Units": "string"
        },
        "seizure_Engel12m": {
            "Description": "Engel outcome classification 12 months post-surgical intervention; integer represents roman numeral classes and .1 = A, .2 = B, .3 = C, .4 = D",
            "Reference": "Wieser HG et al., Epilepsia. 2001 Feb;42(2):282-6. PMID: 11240604.",
            "Units": "number class",
            "Levels": {
                "n/a": "no surgical intervention or unknown"
            }
        },
        "seizure_Engel24m": {
                "Description": "Engel outcome classification 24 months post-surgical intervention; integer represents roman numeral classes and .1 = A, .2 = B, .3 = C, .4 = D",
                "Reference": "Wieser HG et al., Epilepsia. 2001 Feb;42(2):282-6. PMID: 11240604.",
                "Units": "number class",
                "Levels": {
                "n/a": "not available or not applicable (absence of surgical intervention post-implant)"
            }
        },
        "fiveSenseScore": {
            "Description": "5-SENSE Score",
            "Reference": "Astner-Rohracher A et al., JAMA Neurol. 2022 Jan 1;79(1):70-79. doi:10.1001/jamaneurol.2021.4405. PMID:34870697; PMCID:PMC8649918.",
            "Units": "number index",
            "Levels": {
                "n/a": "no surgical intervention or not available"
            }
        }
    })

    participants_sidecar.save(output_dir=f"output/{name}/bids", json_indent=4)

def ceateDatasetDescription(name):
    dd_sidecar = DatasetDescriptionSidecar({
            "Name": f"{name}",
            "BIDSVersion": "1.10.1",
            "DatasetType": "raw",
            "License": "CC-BY",
            "Authors": [
                {
                    "first_name" : "Nishant",
                    "last_name" : "Sinha",
                    "orcid" : "0000-0002-2090-4889",
                    "degree" : "Ph.D."
                },
                {
                    "first_name" : "Erin",
                    "middle_initial" : "C",
                    "last_name" : "Conrad",
                    "orcid" : "0000-0001-8910-1817",
                    "degree" : "M.D."
                },
                {
                    "first_name" : "Kathryn",
                    "middle_initial" : "A",
                    "last_name" : "Davis",
                    "orcid" : "0000-0002-7020-6480",
                    "degree" : "M.D., "
                },
                {
                    "first_name" : "Joost",
                    "middle_initial" : "B",
                    "last_name" : "Wagenaar",
                    "orcid" : "0000-0003-0837-7120",
                    "degree" : "Ph.D., "
                },
                {
                    "first_name" : "Brian",
                    "last_name" : "Litt",
                    "orcid" : "0000-0003-2732-6927",
                    "degree" : "M.D."
                }
            ],
            "Acknowledgements": "This dataset was prepared by the iEEG-BIDS Migration Tool developed at the University of Pennsylvania.",
            "HowToAcknowledge": "Please cite this dataset using the information in the footer found on epilepsy.science",
            "Funding": [
                "National Institue of Neurological Disorders and Stroke of the National Institutes of Health K99NS138680", 
                "National Institue of Neurological Disorders and Stroke of the National Institutes of Health K23NS121401", 
                "National Institue of Neurological Disorders and Stroke of the National Institutes of Health R01NS125137", 
                "National Institue of Neurological Disorders and Stroke of the National Institutes of Health R01NS116504", 
                "National Institue of Neurological Disorders and Stroke of the National Institutes of Health U24NS134536", 
                "National Institue of Neurological Disorders and Stroke of the National Institutes of Health U24NS063930",
                "National Institue of Neurological Disorders and Stroke of the National Institutes of Health R61NS125568",
                "National Institue of Neurological Disorders and Stroke of the National Institutes of Health DP1NS122038",
                "The Burroughs Welcome Fund" 
            ],
            "EthicsApprovals": [
                "University of Pennsylvania Human Research Protections Program, Institutional Review Boards (Protocol 703979, 811097, and/or 821778)"
            ],
            "ReferencesAndLinks": "",
            "GeneratedBy": [
                {
                    "Name": "iEEG-BIDS Migration Tool",
                    "Version": "1.0.0",
                    "Description": "https://github.com/Pennsieve/migrationtools",
                }
            ]
            ,
            "Keywords": ["epilepsy", "intracranial", "human", "adult", "epilepsy.science"]
        })

    dd_sidecar.save(output_dir=f"output/{name}/bids", json_indent=4)

def merge_csvs_by_eps(csv_path_1: str, csv_path_2: str) -> Dict[str, Dict[str, Any]]:
    """
    Merge two CSV files by the 'EPS Number' column.
    Each key in the result dict is an EPS Number, and its value is a merged dict
    of all other columns from both CSVs.

    Example output:
    {
        "EPS000049": {
            "col1_from_csv1": "val1",
            "col2_from_csv1": "val2",
            "col1_from_csv2": "val3",
        }
    }
    """
    path1, path2 = Path(csv_path_1), Path(csv_path_2)

    csv1_data = read_csv_to_dict(path1)
    csv2_data = read_csv_to_dict(path2)

    merged = {}

    # Combine both datasets by EPS Number
    all_eps = set(csv1_data.keys()) | set(csv2_data.keys())

    for eps in all_eps:
        merged[eps] = {}
        merged[eps].update(csv1_data.get(eps, {}))
        merged[eps].update(csv2_data.get(eps, {}))

    return merged

def main():

    print("Fetching all datasets...")
    datasets = get_all_datasets()
    print(f"Total datasets fetched: {len(datasets)}")

    migration_hardware_data_map = multi_dataset_read_csv_to_dict(Path(MASTER_MIGRATION_METADATA))
    migration_subject_map = read_csv_to_dict(Path(MASTER_SUBJECT_METADATA))

    

    for ds in datasets:
        original_name = ds["content"]["name"]
        ds_id = ds["content"]["id"]

        # if not original_name.startswith("PennEPI"):
        if not original_name.startswith("EPS") and not original_name.startswith("PennEPI"):
            continue

        if original_name == "PennEPI00049":
            original_name = "EPS0000049"

        name = rename(original_name)
        print(f"\nProcessing dataset: {name}")
        pkg_data = get_dataset_packages(ds_id)


        ceateDatasetDescription(name)
        createParticipantsSidecar(name)
        createParticipantsTSVSidecar(name,original_name,migration_subject_map)
        createSessionsDataSidecar(name,original_name,migration_subject_map) # TODO: JB to send new CSV
        createIEEGDataSidecar(name,original_name,migration_hardware_data_map) # TODO: Needs to be dataset specific
        createCoordsSidecar(name)
        createElectrodesSidecar(name)

def rename(name):
    digits = ''.join(c for c in name if c.isdigit())
    number = str(int(digits))
    padded = number.zfill(5)
    new_name = f"{PREFIX}{padded}"

    return new_name


main()