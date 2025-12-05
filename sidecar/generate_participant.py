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

def createParticipantsSidecar(name):
    participants_sidecar = ParticipantsSidecar({
    "participant_id": {
        "Description": "PREVeNT Trial unique participant identifier"
    },
    "site_code": {
        "Description": "PREVeNT Trial clinical site codes",
        "Levels": {
            "001": "PREVeNT Trial Site 001",
            "002": "PREVeNT Trial Site 002",
            "003": "PREVeNT Trial Site 003",
            "004": "PREVeNT Trial Site 004",
            "005": "PREVeNT Trial Site 005",
            "006": "PREVeNT Trial Site 006",
            "007": "PREVeNT Trial Site 007",
            "008": "PREVeNT Trial Site 008",
            "009": "PREVeNT Trial Site 009",
            "011": "PREVeNT Trial Site 011",
            "012": "PREVeNT Trial Site 012",
            "013": "PREVeNT Trial Site 013",
            "015": "PREVeNT Trial Site 015"
        }
    },
    "NDAR_GUID": {
        "Description": "National Database for Autism Research (NDAR) Global Unique Identifier",
        "Link": "https://nda.nih.gov/"
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
        "Description": "Biological sex of participant at birth",
        "Levels": {
            "Female": "Female",
            "Male": "Male"
        }
    },
    "tsc_gene": {
        "Description": "results of genetic testing for the TSC1 and TSC2 genes",
        "Levels": {
            "TSC1": "TSC1",
            "TSC2": "TSC2",
            "NMI": "no mutations identified",
            "n/a": "not available"
        }
    },
    "tsc_exon": {
        "Description": "exon"
    },
    "tsc_gene_mutation_detail": {
        "Description": "verbatim report of gene mutation detail"
    },
    "chr_location": {
        "Description": "gene mutation chromosomal location"
    },
    "tsc_mutation": {
        "Description": "cDNA-level change (HGVS c.) position on the reference sequence describing the nucleotide alteration"
    },
    "tsc_pchange": {
        "Description": "protein-level change (p.) position on the reference sequence"
    },
    "variant_type": {
        "Description": ""
    },
    "variant_consequence": {
        "Description": ""
    },
    "variant_pathogenicity": {
        "Description": "",
        "Levels": {
            "pathogenic": "pathogenic",
            "likely pathogenic": "likely pathogenic",
            "variant of uncertain significance": "",
            "likely benign": "likely benign",
            "benign": "benign"
        }
    },
    "variant_interpretation": {
        "Description": "",
        "Levels": {
            "known disease causing": "known disease causing",
            "disease causing": "disease causing",
            "uncertain significance": "uncertain significance",
            "no mutations identified": "no mutations identified"
        }
    },
    "zygosity": {
        "Description": "",
        "Levels": {
            "homozygous": "homozygous",
            "heterozygous": "heterozygous",
            "hemizygous": "hemizygous",
            "compound heterozygous": "compound heterozygous"
        }
    },
    "reference_sequence": {
        "Description": "The specific DNA (e.g., NM_004006.2) or protein sequence used."
    },
    "prv_treatment_grp": {
        "Description": "PREVeNT Treatment group",
        "Levels": {
            "Watchful Waiting": "from enrollment until the emergence of an abnormal EEG with interictal epileptiform discharges",
            "Straight to Open Label": "Participants who subsequently developed clinical and/or electrographic seizures during the 'watchful waiting' period of the study but prior to developing epileptiform abnormalities on the EEG were not randomized. Instead, they immediately began treatment with open label vigabatrin (100 mg/kg/day)",
            "Vigabatrin": "Participants with emergence of specific, predetermined EEG biomarkers (sharps waves, (poly-) spikes), but not seizures would prompt 1:1 randomization to vigabatrin",
            "Placebo": "Participants with emergence of specific, predetermined EEG biomarkers (sharps waves, (poly-) spikes), but not seizures would prompt 1:1 randomization to placebo"
        },
        "Reference": "Bebin, E. M., Peters, J. M., Porter, B. E., McPherson, T. O., O'Kelley, S., Sahin, M., Taub, K. S., Rajaraman, R., Randle, S. C., McClintock, W. M., Koenig, M. K., Frost, M. D., Northrup, H. A., Werner, K., Nolan, D. A., Wong, M., Krefting, J. L., Biasini, F., … Peri, K. (2023). Early Treatment with Vigabatrin Does Not Decrease Focal Seizures or Improve Cognition in Tuberous Sclerosis Complex: The PREVeNT Trial. Annals of Neurology, 95(1), 15–26. Portico. https://doi.org/10.1002/ana.26778"
    },
    "prv_randomization_cohort": {
        "Description": "Randomization Age Cohort in Months",
        "Levels": {
            ">7": "randomized after 7 months of age",
            "<7": "randomized before 7 months of age",
            "Not Randomized": "not randomized"
        },
        "Units": "months"
    },
    "drug_resistant_epilepsy_24m": {
        "Description": "Drug resistant epilepsy at 24 months",
        "Levels": {
            "Yes": "participant had drug resistant epilepy at 24 months of age",
            "No": "participant did not have drug resistant epilepy at 24 months of age",
            "n/a": "drug resistance at 24 months of age not available"
        }
    },
    "epilepsy_control_24m": {
        "Description": "Epilepsy control at 24 months",
        "Levels": {
            "Seizure Free": "Seizure free",
            "Controlled": "Seizures controlled",
            "Nearly Controlled": "Seizures nearly controlled",
            "Partially Controlled": "Seizures partially controlled",
            "Not Controlled": "Seizures not controlled"
        }
    },
    "had_any_seizures_12m": {
        "Description": "Participant had at least one seizure by 12 months of age"
    },
    "had_any_seizures_24m": {
        "Description": "Participant had at least one seizure by 24 months of age"
    },
    "had_any_seizures_36m": {
        "Description": "Participant had at least one seizure by 36 months of age"
    },
    "had_focal_seizures_12m": {
        "Description": "Participant had at least one focal seizure by 12 months of age"
    },
    "had_focal_seizures_24m": {
        "Description": "Participant had at least one focal seizure by 24 months of age"
    },
    "had_focal_seizures_36m": {
        "Description": "Participant had at least one focal seizure by 36 months of age"
    },
    "had_infantile_spasms_12m": {
        "Description": "Participant had infantile spasms by 12 months of age"
    },
    "had_infantile_spasms_24m": {
        "Description": "Participant had infantile spasms by 24 months of age"
    },
    "had_infantile_spasms_36m": {
        "Description": "Participant had infantile spasms by 36 months of age"
    },
    "bayleyiii_12m": {
        "Description": "Bayley Scales of Infant and Toddler Development, Third Edition, Composite Score, administered at the 12 month visit",
        "Version": "Bayley Scales of Infant and Toddler Development, Third Edition (Bayley-III)",
        "Reference": "Michalec, D. (2011). Bayley Scales of Infant Development: Third Edition. In: Goldstein, S., Naglieri, J.A. (eds) Encyclopedia of Child Behavior and Development. Springer, Boston, MA. https://doi.org/10.1007/978-0-387-79061-9_295",
        "Units": "composite score"
    },
    "bayleyiii_24m": {
        "Description": "Bayley Scales of Infant and Toddler Development, Third Edition, Composite Score, administered at the 24 month visit",
        "Version": "Bayley Scales of Infant and Toddler Development, Third Edition (Bayley-III)",
        "Reference": "Michalec, D. (2011). Bayley Scales of Infant Development: Third Edition. In: Goldstein, S., Naglieri, J.A. (eds) Encyclopedia of Child Behavior and Development. Springer, Boston, MA. https://doi.org/10.1007/978-0-387-79061-9_295",
        "Units": "composite score"
    },
    "bayleyiii_36m": {
        "Description": "Bayley Scales of Infant and Toddler Development, Third Edition, Composite Score, administered at the 36 month visit",
        "Version": "Bayley Scales of Infant and Toddler Development, Third Edition (Bayley-III)",
        "Reference": "Michalec, D. (2011). Bayley Scales of Infant Development: Third Edition. In: Goldstein, S., Naglieri, J.A. (eds) Encyclopedia of Child Behavior and Development. Springer, Boston, MA. https://doi.org/10.1007/978-0-387-79061-9_295",
        "Units": "composite score"
    },
    "vinelandii_12m": {
        "Description": "Vineland Adaptive Behavior Scales, Second Edition, Interview Format is a parent-report adaptive measure which assesses social, communication, motor and daily living skills, administered at the 12 month visit",
        "Version": "Vineland Adaptive Behavior Scales, Second Edition (Vineland-II)",
        "Reference": "Sparrow, S., Cicchetti, D., and Balla, D. (2005). Vineland Adaptive Behavior Scales, Second edition. AGS Publishing: Circle Pines, MN.",
        "Units": "scaled score"
    },
    "vinelandii_24m": {
        "Description": "Vineland Adaptive Behavior Scales, Second Edition, Interview Format is a parent-report adaptive measure which assesses social, communication, motor and daily living skills, administered at the 24 month visit",
        "Version": "Vineland Adaptive Behavior Scales, Second Edition (Vineland-II)",
        "Reference": "Sparrow, S., Cicchetti, D., and Balla, D. (2005). Vineland Adaptive Behavior Scales, Second edition. AGS Publishing: Circle Pines, MN.",
        "Units": "scaled score"
    },
    "vinelandii_36m": {
        "Description": "Vineland Adaptive Behavior Scales, Second Edition, Interview Format is a parent-report adaptive measure which assesses social, communication, motor and daily living skills, administered at the 36 month visit",
        "Version": "Vineland Adaptive Behavior Scales, Second Edition (Vineland-II)",
        "Reference": "Sparrow, S., Cicchetti, D., and Balla, D. (2005). Vineland Adaptive Behavior Scales, Second edition. AGS Publishing: Circle Pines, MN.",
        "Units": "scaled score"
    }
})

    participants_sidecar.save(output_dir=f"output/{name}", json_indent=4)

createParticipantsSidecar('participants.json')