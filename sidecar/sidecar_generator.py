from DatsetDescriptionSidecar import DatasetDescriptionSidecar

def main():
    dd_sidecar = DatasetDescriptionSidecar({
        "Name": f"Sample Dataset", 
        "BIDSVersion": "BIDS_VERSION",
        "DatasetType": "raw",
        "License": "LICENSE",
        "Authors": ["ME","AND","YOU", "AND","ZOBOOMAFOO"],
        "Acknowledgements": "ACKNOWLEDGEMENTS",
        "HowToAcknowledge": "HOW_TO_ACKNOWLEDGE",
        "Funding": ["FUNDING_1", "FUNDING_2"],
        "EthicsApprovals": ["ETHICS_APPROVAL_1"],
        "ReferencesAndLinks": "REFERENCE_AND_LINKS",
        "DatasetDOI": "DATASE_DOI",
        "GeneratedBy": [{
            "Name": "iEEG-BIDS Migration Tool",
            "Version": "1.0.0"
        }],
        "Description": "DESCRIPTION",
    })
    if dd_sidecar.validate():
        print("DatasetDescriptionSidecar is valid.")
        dd_sidecar.save(output_dir="output/json", flat=True, json_indent=4)
    else:
        print("DatasetDescriptionSidecar is invalid.")


main()