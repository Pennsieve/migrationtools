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
from channels_tsv_generator import make_channels
from pathlib import Path
from typing import Dict, Any



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

    electrodes_payload = []
    electrode_data = load_data(f"electrode_data_{name}")
    electrode_text = load_data(f"electrode_txt_data_{name}")

    if electrode_data != None:
        for data in electrode_data:
            label = data.get("labels","")
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
                "group": label[:2].upper(),
                "hemisphere": label[0].upper(),
                "type": ELECTRODES_GROUP,
                "dimension": dimension,
                "roi": data.get("roi",""),
            })
        sidecar = ElectrodesSidecar(filename=f"sub-{name}_ses-postimplant_space-MNI152NLin6ASym_electrodes.tsv")
        sidecar.save(data=electrodes_payload, output_dir=f"output/{name}/primary/sub-{name}/ses-postimplant/ieeg")
        return True
    else:
        return False

def createCoordsSidecar(name):
    coord_fields = {
            "IntendedFor": "bids::derivatives/freesurfer/mri/T1.nii.gz",
            "iEEGCoordinateSystem": "MNI152NLin6ASym",
            "iEEGCoordinateUnits": "mm",
            "iEEGCoordinateSystemDescription": "Transformation of electrodes to MNI152NLin2009cAsym standard space",
            "iEEGCoordinateProcessingDescription": "derivatives/ieeg_recon/dataset_description.json: PipelineSteps, Name: Module4_MNI152_Transformation",
            "iEEGCoordinateProcessingReference": "Lucas A, Scheid BH, Pattnaik AR, Gallagher R, Mojena M, Tranquille A, Prager B, Gleichgerrcht E, Gong R, Litt B, Davis KA, Das S, Stein JM, Sinha N. iEEG-recon: A fast and scalable pipeline for accurate reconstruction of intracranial electrodes and implantable devices. Epilepsia. 2024 Mar;65(3):817-829. doi: 10.1111/epi.17863. Epub 2024 Jan 10. PMID: 38148517; PMCID: PMC10948311.",
        }

    sidecar = CoordSystemSidecar(coord_fields,filename=f"sub-{name}_ses-postimplant_space-{coord_fields["iEEGCoordinateSystem"]}_coordsystem.json")
    sidecar.save(output_dir=f"output/{name}/primary/sub-{name}/ses-postimplant/ieeg", json_indent=4)

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
            "SamplingFrequency": sampling_frquency, # TODO: Not being pulled 
            "PowerLineFrequency": POWER_LINE_FREQUENCY, # ok
            "SoftwareFilters": SOFTWARE_FILTERS,  # ok
            "ECOGChannelCount": channel_counts["ECOGChannelCount"],  # ok
            "SEEGChannelCount": channel_counts["SEEGChannelCount"],  # ok
            "EEGChannelCount": channel_counts["EEGChannelCount"],  # ok
            "EOGChannelCount": channel_counts["EOGChannelCount"],  # ok
            "ECGChannelCount": channel_counts["ECGChannelCount"],  # ok
            "EMGChannelCount": channel_counts["EMGChannelCount"],  # ok
            "MiscChannelCount": channel_counts["MiscChannelCount"],  # ok
            "TriggerChannelCount": channel_counts["TriggerChannelCount"],  # TODO: Confirm
            "RecordingDuration": recording_duration, # TODO: Not being pulled
            "RecordingType": RECORDING_TYPE, # ok
            "HardwareFilters":{
                "Hardware bandwidth filter":{
                    "min (Hz)": "0.01",
                    "max (Hz)": "4000",
                }
            }
        }

        sidecar = IeegSidecar(ieeg_data, filename=f"sub-{name}_ses-postimplant_task-clinical_ieeg.json")
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
        eps_key = eps_to_penn_epi(key)
        payload = load_data("payload")
        try:
            if sub_key == None:
                return payload[eps_key]["duration"]
            else:
                return payload[eps_key][sub_key]["duration"]
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
                    elif line["type"].lower().strip() == "trig":
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

            path = f"{OUTPUT_DIR}/{name}/primary/{sub_key}/sub-{name}/ses-postimplant/ieeg"
            channels_path = os.path.join(OUTPUT_DIR, name, sub_key, "primary", f"sub-{name}", "ses-postimplant", "ieeg", f"sub-{name}_ses-postimplant_task-clinical_channels.tsv")
            sampling_frquency = get_sampling_frequency(channels_path)
            recording_duration = get_recording_duration(key,sub_key)
            channel_counts = get_channel_counts(channels_path)

            save_ieeg_sidecar(name, sampling_frquency, recording_duration, channel_counts, data_map.get(key),path)
    else:
        path = f"{OUTPUT_DIR}/{name}/primary/sub-{name}/ses-postimplant/ieeg"
        channels_path = os.path.join(OUTPUT_DIR, name,"primary",f"sub-{name}", "ses-postimplant", "ieeg", f"sub-{name}_ses-postimplant_task-clinical_channels.tsv")
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
                "session_description": "post-surgical treatment followup scan",
                "subject_age_session": "n/a",
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
    session_sidecar = SessionSidecar(filename=f"sub-{name}_sessions.tsv")

    session_sidecar.save(data=sessions_data, output_dir=f"output/{name}/primary/sub-{name}")

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
                "MRI_lesion":data_map[key].get("mri_lesion","n/a"),
                "MRI_lesionType": data_map[key].get("mri_lesionType","n/a"),
                'MRI_lesionDetails':data_map[key].get("mri_lesionDetails","n/a"),
                "ieeg_isFocal": data_map[key].get("ieeg_isFocal","n/a"),
                "intervention_type": data_map[key].get("intervention_type","n/a"),
                "intervention_location":data_map[key].get("intervention_location","n/a"),
                "seizure_Engel12m":data_map[key].get("seizure_Engel12m","n/a"),
                "seizure_Engel24m":data_map[key].get("seizure_Engel24m","n/a"),
                "fiveSenseScore":data_map[key].get("fiveSenseScore","n/a"),
            },

        ]
    pariticpant_sidecar = ParticipantsSideCarTSV(filename=f"participants.tsv")
    pariticpant_sidecar.save(data=pariticpant_data, output_dir=f"output/{name}")

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
        },
        "ieeg_isFocal": {
            "Description": "Postimplant determination of seizure onset focality",
            "Levels": {
                "focal": "focal",
                "nonfocal": "nonfocal"
            }
        },
        "age_intervention":{
            "Description": "Age of subject at postimplant surgical intervention",
            "Units": "years"
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
        },
        "seizure_Engel12m": {
            "Description": "Engel outcome classification 12 months post-surgical intervention; integer represents roman numeral classes and .1 = A, .2 = B, .3 = C, .4 = D",
            "Reference": "Wieser HG, Blume WT, Fish D, Goldensohn E, Hufnagel A, King D, Sperling MR, Lüders H, Pedley TA; Commission on Neurosurgery of the International League Against Epilepsy (ILAE). ILAE Commission Report. Proposal for a new classification of outcome with respect to epileptic seizures following epilepsy surgery. Epilepsia. 2001 Feb;42(2):282-6. PMID: 11240604.",
            "Units": "number class",
        },
        "seizure_Engel24m": {
                "Description": "Engel outcome classification 24 months postsurgical intervention; integer represents roman numeral classes and .1 = A, .2 = B, .3 = C, .4 = D",
                "Reference": "Wieser HG, Blume WT, Fish D, Goldensohn E, Hufnagel A, King D, Sperling MR, Lüders H, Pedley TA; Commission on Neurosurgery of the International League Against Epilepsy (ILAE). ILAE Commission Report. Proposal for a new classification of outcome with respect to epileptic seizures following epilepsy surgery. Epilepsia. 2001 Feb;42(2):282-6. PMID: 11240604.",
                "Units": "number class",
        },
        "fiveSenseScore": {
            "Description": "5-SENSE Score",
            "Reference": "Astner-Rohracher A, Zimmermann G, Avigdor T, Abdallah C, Barot N, Brázdil M, Doležalová I, Gotman J, Hall JA, Ikeda K, Kahane P, Kalss G, Kokkinos V, Leitinger M, Mindruta I, Minotti L, Mizera MM, Oane I, Richardson M, Schuele SU, Trinka E, Urban A, Whatley B, Dubeau F, Frauscher B. Development and Validation of the 5-SENSE Score to Predict Focality of the Seizure-Onset Zone as Assessed by Stereoelectroencephalography. JAMA Neurol. 2022 Jan 1;79(1):70-79. doi: 10.1001/jamaneurol.2021.4405. PMID: 34870697; PMCID: PMC8649918.",
            "Units": "number index",
        }
    })

    participants_sidecar.save(output_dir=f"output/{name}", json_indent=4)

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
            "Keywords": ["epilepsy", "intracranial", "human", "adult", "epilepsy.science"]
        })

    dd_sidecar.save(output_dir=f"output/{name}", json_indent=4)

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

    
    if not os.path.exists("cache"):
        print("Fetching channels")
        make_channels()

    print("Fetching all datasets...")
    datasets = get_all_datasets()
    print(f"Total datasets fetched: {len(datasets)}")

    migration_hardware_data_map = multi_dataset_read_csv_to_dict(Path(MASTER_MIGRATION_METADATA))
    migration_subject_map = read_csv_to_dict(Path(MASTER_SUBJECT_METADATA))

    for ds in datasets:
        original_name = ds["content"]["name"]
        

        if not original_name.startswith("PennEPI"):
            continue

        penn_epi_name = original_name
        print(f"\nProcessing dataset: {penn_epi_name}")
        if penn_epi_name not in ["PennEPI00102", "PennEPI00098", "PennEPI00093", "PennEPI00090", "PennEPI00082", "PennEPI00087", "PennEPI00138", "PennEPI00091", "PennEPI00096", "PennEPI00137", "PennEPI00095", "PennEPI00088", "PennEPI00086", "PennEPI00099", "PennEPI00083",]:
            print(f"Skipping dataset: {penn_epi_name}")
            continue
        eps_name = penn_epi_to_eps(original_name)

        ceateDatasetDescription(penn_epi_name)
        createParticipantsSidecar(penn_epi_name)
        createParticipantsTSVSidecar(penn_epi_name,eps_name,migration_subject_map)
        createSessionsDataSidecar(penn_epi_name,eps_name,migration_subject_map)
        createIEEGDataSidecar(penn_epi_name,eps_name,migration_hardware_data_map)
        created_electrodes = createElectrodesSidecar(penn_epi_name)
        if penn_epi_name in ["PennEPI00102", "PennEPI00098", "PennEPI00093", "PennEPI00090", "PennEPI00082", "PennEPI00087", "PennEPI00138", "PennEPI00091", "PennEPI00096", "PennEPI00137", "PennEPI00095", "PennEPI00088", "PennEPI00086", "PennEPI00099", "PennEPI00083"]:
            print(f"{penn_epi_name} Was electrodes created: {created_electrodes}")
        if created_electrodes:
            createCoordsSidecar(penn_epi_name)
        

def rename(name):
    digits = ''.join(c for c in name if c.isdigit())
    number = str(int(digits))
    padded = number.zfill(5)
    new_name = f"{PREFIX}{padded}"

    return new_name


main()