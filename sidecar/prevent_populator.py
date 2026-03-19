#!/usr/bin/env python3
"""
PREVeNT Record Populator

Wrapper around omop_populator.py that uses PREVeNT-specific mappings.

Usage:
  # Dry run for one dataset
  python prevent_populator.py --api-key KEY --api-secret SECRET \
      --datasets PREVeNT_DATASET_NAME \
      --models person genetics seizure_hx bayley_iii vineland \
      --dry-run

  # Run for real
  python prevent_populator.py --api-key KEY --api-secret SECRET \
      --datasets PREVeNT_DATASET_NAME \
      --models all
"""

import sys
from pathlib import Path

# Patch the MAPPINGS_FILE before importing OMOPPopulator
SCRIPT_DIR = Path(__file__).parent
PREVENT_MAPPINGS = SCRIPT_DIR / "PREVeNT" / "prevent_mappings.json"

# Monkey-patch the module variable
import sidecar.omop_populator as omop_module
omop_module.MAPPINGS_FILE = PREVENT_MAPPINGS

# Now import and run
from sidecar.omop_populator import main

if __name__ == '__main__':
    print(f"Using PREVeNT mappings: {PREVENT_MAPPINGS}")
    main()
