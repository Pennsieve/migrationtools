#!/usr/bin/env python3
"""
Manage PennEPI Datasets - Update metadata and archive files

This script:
1. Loops through all PennEPI datasets
2. Updates contributors, title, subtitle, and description
3. Archives .tsv and .json files (excluding those under 'derivative' collections)
"""

import os
import sys
import json
import logging
import requests
from typing import Dict, List, Set, Optional, Tuple
from helpers import *
from dataclasses import dataclass


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class PackageNode:
    """Represents a package/collection in the tree structure"""
    id: str
    name: str
    package_type: str
    parent_id: Optional[str] = None
    children: List[str] = None
    
    def __post_init__(self):
        if self.children is None:
            self.children = []


class PennsieveDatasetManager:
    """Manages operations on Pennsieve datasets"""
    
    def __init__(self, api_key: str, dry_run: bool = False):
        self.api_key = api_key
        self.dry_run = dry_run
        self.base_url = "https://api.pennsieve.io"
        
    def _make_request(self, method: str, url: str, **kwargs) -> Optional[Dict]:
        """Make API request with error handling"""
        try:
            response = requests.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json() if response.text else None
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response: {e.response.text}")
            return None
    
    def get_datasets(self, search=None) -> List[Dict]:
        """Fetch all PennEPI datasets"""
        result = load_data("datasets")
        if result is None:
            print("Fetching all packages from network...")
            datasets = get_all_datasets()
            save_data(datasets, "datasets")
        
        if not search:
            # Filter for PennEPI datasets
            pennepi_datasets = [
                ds for ds in result 
                if ds.get('content', {}).get('name', '').startswith('PennEPI')
            ]
            logger.info(f"Found {len(pennepi_datasets)} PennEPI datasets")
            return pennepi_datasets
        else:
            dataset = [
                ds for ds in result 
                if ds.get('content', {}).get('name', '') == search
            ]
            logger.info(f"Found {search} dataset")
            return dataset
        
        
    
    def update_contributors(self, dataset_id: str) -> bool:
        """
        Update dataset contributors
        
        Process:
        1. Delete contributor 19 (if exists)
        2. Add contributors [32, 31, 18, 9, 8] in order
        
        Args:
            contributors: Ignored - we use fixed contributor list
        """
        logger.info(f"Updating contributors for dataset {dataset_id}")
        
        # Fixed contributor IDs in order
        CONTRIBUTOR_IDS = [32, 31, 18, 9, 8]
        CONTRIBUTOR_TO_REMOVE = 19
        
        if self.dry_run:
            logger.info(f"  DRY RUN: Would remove contributor {CONTRIBUTOR_TO_REMOVE}")
            logger.info(f"  DRY RUN: Would add contributors: {CONTRIBUTOR_IDS}")
            return True
        
        # Delete contributor 19
        delete_url = f"{self.base_url}/datasets/{dataset_id}/contributors/{CONTRIBUTOR_TO_REMOVE}?api_key={self.api_key}"
        logger.info(f"  Removing contributor {CONTRIBUTOR_TO_REMOVE}...")
        
        try:
            response = requests.delete(delete_url)
            if response.status_code == 404:
                logger.info(f"    Contributor {CONTRIBUTOR_TO_REMOVE} not found (OK)")
            elif response.status_code in [200, 204]:
                logger.info(f"    Removed contributor {CONTRIBUTOR_TO_REMOVE}")
            else:
                logger.warning(f"    Unexpected status {response.status_code} when deleting contributor")
        except requests.exceptions.RequestException as e:
            logger.warning(f"    Error deleting contributor (continuing anyway): {e}")
        
        # Add contributors one by one
        success = True
        for contributor_id in CONTRIBUTOR_IDS:
            url = f"{self.base_url}/datasets/{dataset_id}/contributors?api_key={self.api_key}"
            payload = {"contributorId": contributor_id}
            
            logger.info(f"  Adding contributor {contributor_id}...")
            result = self._make_request("PUT", url, json=payload)
            
            if result is None:
                logger.error(f"    Failed to add contributor {contributor_id}")
                success = False
                # Should we continue or abort here?
                # Currently continuing to add remaining contributors
            else:
                logger.info(f"    Added contributor {contributor_id}")
        
        return success
    
    
    def update_metadata(self, dataset_id: str, description: str,tags,dataset_name) -> bool:
        logger.info(f"Updating title for dataset {dataset_id}")
        if self.dry_run:
            logger.info(f"  DRY RUN: Would update title to: {description}")
            return True
        else:
            url = f"{self.base_url}/datasets/{dataset_id}?api_key={self.api_key}"
            payload = {
                "description": description,
                "tags":tags,
                "name": dataset_name
                }
            
            self._make_request("PUT", url, json=payload)

            return True
        
    def update_owner(self, dataset_id: str) -> bool:
        logger.info(f"Updating owner for {dataset_id}")

        # Make Nishant owner
        url = f"{self.base_url}/datasets/{dataset_id}/collaborators/owner?api_key={self.api_key}"
        payload = {
            "id": "N:user:29972d12-8aa3-47a9-bc65-a07a3499a2f7", # Nishant
            "role": "owner"
        }
        self._make_request("PUT", url, json=payload)

        return True
        
    def update_readme(self, dataset_id: str, text: str) -> bool:
        logger.info(f" Updating readme for dataset {dataset_id}")
        if self.dry_run:
            logger.info(f"  DRY RUN: Would update description to: {text}")
            return True
        else:
            url = f"{self.base_url}/datasets/{dataset_id}/readme?api_key={self.api_key}"
            payload = {"readme": text,}
            
            self._make_request("PUT", url, json=payload)

            return True
    
    def update_description(self, dataset_id: str, description: str) -> bool:
        """Update dataset description (DUMMY - implement later)"""
        logger.info(f"[DUMMY] Updating description for dataset {dataset_id}")
        if self.dry_run:
            logger.info(f"  DRY RUN: Would update description to: {description}")
            return True
        
        # TODO: Implement actual API call
        # url = f"{self.base_url}/datasets/{dataset_id}?api_key={self.api_key}"
        # payload = {"description": description}
        # return self._make_request("PUT", url, json=payload) is not None
        return True
    
    def get_or_create_archive_folder(self, dataset_id: str,dataset_name: str) -> Optional[str]:
        """Get or create the archive collection folder"""
        logger.info(f"Ensuring archive folder exists for dataset {dataset_id}")
        archive_id = None
        packages = load_data(f"package_{dataset_name}")
        if packages is None:
            print("Fetching all packages from network...")
            packages = get_dataset_packages(dataset_id)
            save_data(packages, f"package_{dataset_name}")

        for package in packages:
            if package['content']['name'].lower() != "archive":
                continue

            if (package['content']['name'].lower() == "archive" and 
                package['content'].get('packageType') == "Collection" and
                package['content'].get("parentID") is None):
                archive_id = package['content']['nodeId']
                logger.info(f"  Found existing archive folder: {archive_id}")
                return archive_id
        
        # Create archive folder
        url = f"{self.base_url}/packages?api_key={self.api_key}"
        payload = {
            "name": "archive",
            "dataset": dataset_id,
            "packageType": "Collection"
        }
        
        result = self._make_request("POST", url, json=payload)
        if result and 'content' in result:
            archive_id = result['content']['id']
            logger.info(f"  Created archive folder: {archive_id}")
            return archive_id
        
        logger.error("  Failed to create archive folder")
        return None
    
    def build_package_tree(self, dataset_id: str, dataset_name) -> Dict[str, PackageNode]:
        """Build a tree structure of all packages in the dataset"""
        logger.info(f"Building package tree for dataset {dataset_id}")
        
        packages = load_data(f"package_{dataset_name}")
        
        # Build the tree
        nodes = {}
        for pkg in packages:
            node = PackageNode(
                id=pkg['content']['id'],
                name=pkg['content']['name'],
                package_type=pkg['content'].get('packageType', 'Unknown'),
                parent_id=pkg['content'].get('parentId')
            )
            nodes[node.id] = node
        
        # Build parent-child relationships
        for node in nodes.values():
            if node.parent_id and node.parent_id in nodes:
                nodes[node.parent_id].children.append(node.id)
        
        logger.info(f"  Built tree with {len(nodes)} nodes")
        return nodes
    
    def is_under_derivative(self, package_id: str, tree: Dict[str, PackageNode]) -> bool:
        """Check if a package is anywhere under a 'derivative' collection"""
        if package_id not in tree:
            return False
        
        current = tree[package_id]
        visited = set()  # Prevent infinite loops in case of circular references
        
        while current.parent_id:
            if current.parent_id in visited:
                logger.warning(f"Circular reference detected at {current.id}")
                break
            visited.add(current.parent_id)
            
            parent = tree.get(current.parent_id)
            if not parent:
                break
            
            if parent.name.lower() == "derivative" and parent.package_type == "Collection":
                return True
            
            current = parent
        
        return False
    
    def should_archive_package(self, pkg: Dict, parent_lookup: Dict[int, Dict]) -> bool:
        """
        Determine if a package should be archived based on rules:
        
        1. If name in ["partcipants.json", "dataset_description.json", "partcipants.tsv"]
           AND parent is Collection named "primary" → archive
           
        2. If name ends with "_D0X.[extension]" (where X is digit)
           AND parent is Collection named "primary" → archive
           
        3. If name matches "sub-EPSXXXXXXX-postimplant_channels.tsv" or 
           "sub-EPSXXXXXXX-postimplant_ieeg.json"
           AND parent is Collection named "ieeg" OR "D0X" → archive
        """
        import re
        
        content = pkg['content']
        name = content['name']
        parent_id = content.get('parentId')
        
        # If no parent, skip
        if not parent_id:
            return False
        
        # Get parent info
        parent = parent_lookup.get(parent_id)
        if not parent:
            return False
        
        parent_name = parent['name']
        parent_type = parent['packageType']
        
        # Rule 1: Specific filenames with "primary" parent
        if name in ["partcipants.json", "dataset_description.json", "partcipants.tsv"]:
            # breakpoint()
            if parent_type == "Collection" and parent_name == "primary":
                logger.debug(f"  Match Rule 1: {name} in primary collection")
                return True
        
        # Rule 2: Files ending with _D0X.[extension] with "primary" parent
        # Matches: _D0.json, _D01.json, _D02.tsv, etc.
        if re.match(r'.*_D0\d*\.\w+$', name):
            # breakpoint()
            if parent_type == "Collection" and parent_name == "primary":
                logger.debug(f"  Match Rule 2: {name} ends with _D0X")
                return True
        
        # Rule 3: Post-implant files in "ieeg" or "D0X" collections
        if (re.match(r'sub-EPS\d{7}-(post)?implant_channels\.tsv$', name) or
            re.match(r'sub-EPS\d{7}-(post)?implant_ieeg\.json$', name)):
            # breakpoint()
            # Check if parent is "ieeg" or matches "D0X" pattern
            if parent_type == "Collection":
                if parent_name == "ieeg" or re.match(r'D0\d+$', parent_name):
                    logger.debug(f"  Match Rule 3: {name} in {parent_name} collection")
                    return True
        
        return False
    
    def find_files_to_archive(self, dataset_id: str,dataset_name) -> Tuple[List[str], Dict[str, str]]:
        """
        Find files that should be archived based on naming and parent rules
        
        Returns:
            Tuple of (list of package node IDs to archive, dict of node_id -> filename for logging)
        """
        logger.info(f"Finding files to archive in dataset {dataset_id}")
        
        packages = load_data(f"package_{dataset_name}")
        if packages is None:
            print("Fetching all packages from network...")
            packages = get_dataset_packages(dataset_id)
            save_data(packages, f"package_{dataset_name}")
        if not packages:
            return [], {}
        
        # Build parent lookup for quick checks
        parent_lookup = self.build_parent_lookup(packages)
        
        to_archive = []
        file_info = {}
        
        for pkg in packages:
            content = pkg['content']
            
            # Skip collections, only look at files
            if (content['packageType'] == "Collection" or
                content["name"].startswith("__DELETED__") or
                not content["name"].lower().endswith(('.json', '.tsv'))):
                continue
            
            # Check if should be archived
            if self.should_archive_package(pkg, parent_lookup):
                node_id = content['nodeId']
                to_archive.append(node_id)
                file_info[node_id] = content['name']
                logger.info(f"  Will archive: {content['name']}")
        
        logger.info(f"  Found {len(to_archive)} files to archive")
        return to_archive, file_info
    
    def build_parent_lookup(self, packages: List[Dict]) -> Dict[int, Dict]:
        """
        Build a simple lookup: package_id -> {name, packageType}
        
        Returns:
            Dict mapping numeric package ID to package info
        """
        lookup = {}
        for pkg in packages:
            pkg_id = pkg['content']['id']
            lookup[pkg_id] = {
                'name': pkg['content']['name'],
                'packageType': pkg['content']['packageType']
            }
        
        return lookup
    
    
    def move_files_to_archive(self, archive_id: str, package_ids: List[str], 
                              file_info: Dict[str, str]) -> bool:
        """Move multiple packages to the archive folder"""
        if not package_ids:
            logger.info("  No files to move")
            return True
        
        logger.info(f"Moving {len(package_ids)} files to archive {archive_id}")
        
        if self.dry_run:
            logger.info("  DRY RUN: Would move the following files:")
            for pkg_id in package_ids:
                logger.info(f"    - {file_info.get(pkg_id, pkg_id)}")
            return True
        
        # Move files in batches (API might have limits)
        batch_size = 50  # Adjust based on API limits
        success = True
        
        for i in range(0, len(package_ids), batch_size):
            batch = package_ids[i:i+batch_size]
            
            url = f"{self.base_url}/data/move?api_key={self.api_key}"
            payload = {
                "destination": archive_id,
                "things": batch
            }
            
            result = self._make_request("POST", url, json=payload)
            if result is None:
                logger.error(f"  Failed to move batch {i//batch_size + 1}")
                success = False
            else:
                for pkg_id in batch:
                    logger.info(f"  Moved: {file_info.get(pkg_id, pkg_id)}")
        
        return success
    
    def process_dataset(self, dataset: Dict) -> bool:
        """Process a single dataset with all operations"""
        dataset_id = dataset['content']['id']
        dataset_name = dataset['content']['name']
        if dataset_name in ["PenEPI00001","PennEPI00002","PenEPI00003","PenEPI00004","PenEPI00005","PenEPI00006",
                            "PenEPI00001","PennEPI00008","PennEPI00009","PennEPI00010","PennEPI00011","PennEPI00012",
                            "PennEPI00049"
                            ]:
            logger.info(f"Skipping dataset {dataset_name} as per exclusion list")
            return True
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing dataset: {dataset_name} ({dataset_id})")
        logger.info(f"{'='*60}")
        
        success = True
        
        # Update metadata (using dummy values for now)
        try:
            
            eps_number = penn_epi_to_eps(dataset_name)
            migration_hardware_data_map = multi_dataset_read_csv_to_dict(Path(MASTER_MIGRATION_METADATA))
            dataset_row = migration_hardware_data_map.get(eps_number)
            original_hup_number = dataset_row["ieeg.org dataset name"]

            description = "Multimodal dataset for a single subject that underwent intracranial evaluation for medication-resistant focal epilepsy."
            readme_text = f"Previously published on ieeg.org as {original_hup_number}, this dataset has been supplemented with metadata, imaging, derivatives and republished on Epilepsy.Science using semi-automated migration methods."
            tags = ["epilepsy", "epilepsy.science", "auto-migration", "intracranial", "human", "adult"]
            
            self.update_contributors(dataset_id)
            self.update_metadata(dataset_id,description,tags,dataset_name)
            self.update_readme(dataset_id,readme_text)
            self.update_owner(dataset_id)
        except Exception as e:
            logger.error(f"Failed to update metadata: {e}")
            success = False
        
        # Archive files
        try:
            archive_id = self.get_or_create_archive_folder(dataset_id,dataset_name)
            if not archive_id:
                logger.error("Could not get/create archive folder")
                return False
            
            package_ids, file_info = self.find_files_to_archive(dataset_id,dataset_name)
            if package_ids:
                if not self.move_files_to_archive(archive_id, package_ids, file_info):
                    success = False
        except Exception as e:
            logger.error(f"Failed to archive files: {e}")
            success = False
        
        except Exception as e:
            logger.error(f"Failed to archive files: {e}")
            success = False
        
        return success

def main():
    """Main execution function"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Manage PennEPI datasets - update metadata and archive files'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Run without making actual changes'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    parser.add_argument(
        '--dataset',
        help='Process only a specific dataset ID (for testing)'
    )
    
    args = parser.parse_args()
    
    # Set logging level
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # Get API key from environment
    api_key = os.getenv('PENNSIEVE_API_KEY')
    if not api_key:
        logger.error("PENNSIEVE_API_KEY environment variable not set")
        sys.exit(1)
    
    logger.info(f"Starting PennEPI dataset management")
    logger.info(f"Dry run: {args.dry_run}")
    
    # Initialize manager
    manager = PennsieveDatasetManager(api_key, dry_run=args.dry_run)
    
    # Get datasets
    if args.dataset:
        dataset_payload = manager.get_datasets(args.dataset)
    else:
        dataset_payload = manager.get_datasets()
    
    if not dataset_payload:
        logger.error("No PennEPI datasets found")
        sys.exit(1)
    
    # Process each dataset
    total = len(dataset_payload)
    succeeded = 0
    failed = 0
    
    for idx, dataset in enumerate(dataset_payload, 1):
        logger.info(f"\nProcessing dataset {idx}/{total}")
        if manager.process_dataset(dataset):
            succeeded += 1
        else:
            failed += 1
    
    # Summary
    logger.info(f"\n{'='*60}")
    logger.info(f"SUMMARY")
    logger.info(f"{'='*60}")
    logger.info(f"Total datasets: {total}")
    logger.info(f"Succeeded: {succeeded}")
    logger.info(f"Failed: {failed}")
    
    if failed > 0:
        sys.exit(1)


if __name__ == '__main__':
    main()