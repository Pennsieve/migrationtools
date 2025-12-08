from typing import Dict, Any
from .Sidecar import Sidecar


class DatasetDescriptionJSON(Sidecar):
    """
    Represents the dataset_description.json BIDS sidecar.

    Contains metadata about the dataset including name, version, authors, etc.
    """

    filename = "dataset_description.json"
    default_bids_path = "output_sidecars/"

    REQUIRED_FIELDS = {"Name", "BIDSVersion"}
    RECOMMENDED_FIELDS = {"DatasetType", "License", "Authors", "Acknowledgements", "HowToAcknowledge", "Funding", "EthicsApprovals", "ReferencesAndLinks"}
    OPTIONAL_FIELDS = {"Keywords"}

    DEFAULTS = {
        "BIDSVersion": "1.10.1",
        "DatasetType": "raw",
        "License": "CC-BY",
        "Authors": [
            {
                "first_name": "E. Martina",
                "last_name": "Bebin",
                "orcid": "0000-0003-1264-3428",
                "affiliation": "Department of Neurology, University of Alabama at Birmingham, Birmingham, AL, USA"
            },
            {
                "first_name": "Jurriaan",
                "middle_initial": "M",
                "last_name": "Peters",
                "orcid": "0000-0002-6725-2814",
                "affiliation": "Department of Neurology, Boston Children's Hospital, Harvard Medical School, Boston, MA, USA"
            },
            {
                "first_name": "Brenda",
                "middle_initial": "E",
                "last_name": "Porter",
                "orcid": "0000-0001-6346-7327",
                "affiliation": "Department of Neurology, Stanford University, Stanford, CA, USA"
            },
            {
                "first_name": "Tarrant",
                "middle_initial": "O",
                "last_name": "McPherson",
                "orcid": "0000-0003-3579-5205",
                "affiliation": "Department of Biostatistics and Bioinformatics, Emory University, Atlanta, GA, USA"
            },
            {
                "first_name": "Mustafa",
                "last_name": "Sahin",
                "orcid": "0000-0001-7044-2953",
                "affiliation": "Department of Neurology, Boston Children's Hospital, Harvard Medical School, Boston, MA, USA; Rosamund Stone Zander Translational Neuroscience Center, Boston Children's Hospital, Harvard Medical School, Harvard University, Boston, MA, USA"
            },
            {
                "first_name": "Katherine",
                "middle_initial": "S",
                "last_name": "Taub",
                "orcid": "",
                "affiliation": "Department of Pediatrics, Children's Hospital of Philadelphia, Philadelphia, PA, USA"
            },
            {
                "first_name": "Rajsekar",
                "last_name": "Rajaraman",
                "orcid": "",
                "affiliation": "Department of Pediatrics and Psychiatry and Biobehavioral Sciences, University of California, Los Angeles, Los Angeles, CA, USA"
            },
            {
                "first_name": "Stephanie",
                "middle_initial": "C",
                "last_name": "Randle",
                "orcid": "0009-0009-1556-6940",
                "affiliation": "Department of Pediatrics, Division Pediatric Neurology and Epilepsy, Seattle Children's Hospital, Seattle, WA, USA"
            },
            {
                "first_name": "William",
                "middle_initial": "M",
                "last_name": "McClintock",
                "orcid": "",
                "affiliation": "Department of Pediatrics, Division of Neurology, Children's National Medical Center, Washington, DC, USA"
            },
            {
                "first_name": "Mary Kay",
                "last_name": "Koenig",
                "orcid": "0000-0001-5126-8515",
                "affiliation": "Department of Pediatrics, McGovern Medical School at University of Texas Health Science Center at Houston and Children's Memorial Hermann Hospital, Houston, TX, USA"
            },
            {
                "first_name": "Mike",
                "middle_initial": "D",
                "last_name": "Frost",
                "orcid": "",
                "affiliation": "Minnesota Epilepsy Group, P.A., Minnesota Epilepsy Group, Roseville, MN, USA"
            },
            {
                "first_name": "Hope",
                "middle_initial": "A",
                "last_name": "Northrup",
                "orcid": "0000-0002-2892-0840",
                "affiliation": "Department of Pediatrics, McGovern Medical School at University of Texas Health Science Center at Houston and Children's Memorial Hermann Hospital, Houston, TX, USA"
            },
            {
                "first_name": "Klaus",
                "last_name": "Werner",
                "orcid": "",
                "affiliation": "Department of Pediatrics, Duke University, Durham, NC, USA"
            },
            {
                "first_name": "Danielle",
                "middle_initial": "A",
                "last_name": "Nolan",
                "orcid": "0000-0003-1804-0759",
                "affiliation": "Beaumont Florence and Richard McBrien Pediatric Neuroscience Center, Beaumont Hospital, Royal Oak, MI, USA"
            },
            {
                "first_name": "Michael",
                "last_name": "Wong",
                "orcid": "0000-0002-3796-743X",
                "affiliation": "Department of Neuroscience, Washington University in Saint Louis, Saint Louis, MO, USA"
            },
            {
                "first_name": "Jessica",
                "middle_initial": "L",
                "last_name": "Krefting",
                "orcid": "",
                "affiliation": "Department of Neurology, University of Alabama at Birmingham, Birmingham, AL, USA"
            },
            {
                "first_name": "Gary",
                "last_name": "Cutter",
                "orcid": "",
                "affiliation": "Department of Biostatistics, University of Alabama at Birmingham, Birmingham, AL, USA"
            },
            {
                "first_name": "Darcy",
                "middle_initial": "A",
                "last_name": "Krueger",
                "orcid": "0000-0002-7250-7391",
                "affiliation": "Department of Pediatrics, University of Cincinnati, Cincinnati, OH, USA"
            },
            {
                "first_name": "PREVeNT Study Group"
            }
        ],
        "Acknowledgements": "Special gratitude and recognition go to the TSC families and especially the infants with TSC that participated. Without the support and dedication of the TSC Community and TSC Alliance to the PREVeNT Trial, this effort would not have been possible. We would like to thank Lundbeck Inc. for generously providing the Sabril for the PREVeNT Trial, the TSC Alliance for supplemental funding for data analysis, and Bcureful and Pediatric Epilepsy Research Foundation (PERF) for participant travel support. Research reported in this publication was supported by the National Institute of Neurological Diseases and Stroke of the National Institutes of Health (NINDS) under the award number NCT028494571. The content is solely the responsibility of the authors and does not necessarily represent the official views of the National Institutes of Health.",
        "HowToAcknowledge": "Please cite the referenced paper (https://doi.org/10.1002/ana.26778) and this dataset's DOI provided on epilepsy.science.",
        "Funding": [
            "National Institue of Neurological Disorders and Stroke of the National Institutes of Health U01NS092595",
            "National Institue of Neurological Disorders and Stroke of the National Institutes of Health NCT028494571"
        ],
        "EthicsApprovals": [
            "The study was approved by a central institutional review board (IRB) and each participating site's IRB. Informed consent was obtained for each participant at the time of enrollment."
        ],
        "ReferencesAndLinks": [
            "Bebin, E. M., Peters, J. M., Porter, B. E., McPherson, T. O., O'Kelley, S., Sahin, M., Taub, K. S., Rajaraman, R., Randle, S. C., McClintock, W. M., Koenig, M. K., Frost, M. D., Northrup, H. A., Werner, K., Nolan, D. A., Wong, M., Krefting, J. L., Biasini, F., ... Peri, K. (2023). Early Treatment with Vigabatrin Does Not Decrease Focal Seizures or Improve Cognition in Tuberous Sclerosis Complex: The PREVeNT Trial. Annals of Neurology, 95(1), 15-26. Portico. https://doi.org/10.1002/ana.26778",
            "Farach, L. S., Richard, M. A., Wulsin, A. C., Bebin, E. M., Krueger, D. A., Sahin, M., Porter, B. E., McPherson, T. O., Peters, J. M., O'Kelley, S., Taub, K. S., Rajaraman, R., Randle, S. C., McClintock, W. M., Koenig, M. K., Frost, M. D., Werner, K., Nolan, D. A., Wong, M., ... Salazar, E. (2024). Drug-Resistant Epilepsy in Tuberous Sclerosis Complex Is Associated With TSC2 Genotype: More Findings From the Preventing Epilepsy Using Vigatrin (PREVeNT) Trial. Pediatric Neurology, 159, 62-71. https://doi.org/10.1016/j.pediatrneurol.2024.06.012",
            "O'Kelley, S. E., Capal, J. K., McPherson, T. O., Patrick, K. E., Pearson, D. A., Davis, P. E., Currans, K., Byars, A. W., Porter, B. E., Sahin, M., Taub, K. S., Rajaraman, R., Randle, S., McClintock, W. M., Koenig, M. K., Frost, M. D., Werner, K., Nolan, D. A., Wong, M., ... Bebin, E. M. (2025). Neurodevelopmental Outcomes From the PREVeNT Trial. Pediatric Neurology, 173, 88-97. https://doi.org/10.1016/j.pediatrneurol.2025.09.006"
        ],
        "Keywords": [
            "PREVeNT Trial",
            "tuberous sclerosis complex",
            "developmental outcomes",
            "preventing epilepsy",
            "vigabatrin",
            "eeg",
            "human",
            "pediatric",
            "epilepsy.science"
        ]
    }

    def __init__(self, fields: Dict[str, Any] = None, **kwargs):
        """
        Initialize DatasetDescriptionJSON with fields.

        Args:
            fields: Dictionary of fields. Only "Name" is typically provided,
                   all other fields use defaults.
        """
        if fields is None:
            fields = {}

        # Merge fields with defaults, ensuring Name comes first
        # Start with fields (which contains Name), then add defaults
        merged_fields = {**fields, **self.DEFAULTS}
        # Override defaults with any explicitly provided fields
        merged_fields.update(fields)

        super().__init__(fields=merged_fields, **kwargs)

    def validate(self):
        """
        Validate the dataset_description.json data structure.
        """
        # Check for required fields
        missing_required = self.REQUIRED_FIELDS - self.data.keys()
        if missing_required:
            raise ValueError(f"Missing REQUIRED fields: {sorted(missing_required)}")

        # Warn about missing recommended fields
        missing_recommended = self.RECOMMENDED_FIELDS - self.data.keys()
        if missing_recommended:
            self.log.warning(f"Missing RECOMMENDED fields: {sorted(missing_recommended)}")

        self.log.info(f"{self.__class__.__name__} validation passed.")
        return True
