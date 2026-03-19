#!/usr/bin/env python3
"""
Download one MEF file per PennEPI dataset (and per D0X folder when present).

The script reuses the Pennsieve helper utilities in sidecar/helpers.py to fetch
dataset/package metadata and download signed URLs for MEF files stored under
each dataset's ``ieeg`` collection.
"""

from __future__ import annotations

import argparse
import logging
import re
from collections import defaultdict, deque
from pathlib import Path
from typing import Deque, Dict, Iterable, List, Optional, Tuple

import requests

from sidecar import helpers


LOG = logging.getLogger("mef-downloader")
MEF_SUFFIX = ".mef"
D_FOLDER_PATTERN = re.compile(r"^D0\d+$", re.IGNORECASE)


class PennEpiMefDownloader:
    """Collect a single MEF sample from each PennEPI dataset."""

    def __init__(
        self,
        output_dir: Path,
        datasets_filter: Optional[Iterable[str]] = None,
        limit: Optional[int] = None,
        refresh_cache: bool = False,
        overwrite: bool = False,
        request_timeout: int = 60,
    ) -> None:
        if not helpers.API_KEY:
            raise RuntimeError("PENNSIEVE_API_KEY is required in the environment.")

        self.output_dir = output_dir
        self.limit = limit
        self.refresh_cache = refresh_cache
        self.overwrite = overwrite
        self.timeout = request_timeout
        self.datasets_filter = {name for name in datasets_filter} if datasets_filter else None
        self.session = requests.Session()

    def run(self) -> List[Dict[str, str]]:
        """Execute the downloader and return a summary of saved files."""
        datasets = self._load_datasets()
        LOG.info("Processing %s datasets", len(datasets))

        downloaded: List[Dict[str, str]] = []
        for dataset in datasets:
            try:
                downloaded.extend(self._process_dataset(dataset))
            except Exception as exc:  # pylint: disable=broad-except
                LOG.exception("Failed to process dataset %s: %s", dataset_name(dataset), exc)

        if not downloaded:
            LOG.warning("No MEF files were downloaded.")
        else:
            LOG.info("Downloaded %s MEF files into %s", len(downloaded), self.output_dir)
        return downloaded

    def _load_datasets(self) -> List[Dict]:
        cache = None if self.refresh_cache else helpers.load_data("datasets")
        if cache is None:
            LOG.info("Fetching dataset catalog from Pennsieve...")
            cache = helpers.get_all_datasets()
            helpers.save_data(cache, "datasets")

        datasets: List[Dict] = []
        for entry in cache:
            name = dataset_name(entry)
            if not name.startswith(helpers.PREFIX):
                continue
            if self.datasets_filter and name not in self.datasets_filter:
                continue
            datasets.append(entry)
            if self.limit and len(datasets) >= self.limit:
                break

        return datasets

    def _process_dataset(self, dataset: Dict) -> List[Dict[str, str]]:
        name = dataset_name(dataset)
        LOG.info("Dataset %s", name)

        dataset_dir = self.output_dir / name
        if dataset_dir.exists() and not self.overwrite:
            LOG.info("Skipping %s because %s already exists", name, dataset_dir)
            return []

        packages = self._load_packages(dataset)
        if not packages:
            LOG.warning("No packages returned for %s", name)
            return []

        id_map, children = self._build_package_maps(packages)
        ieeg_nodes = [
            pkg
            for pkg in id_map.values()
            if pkg.get("packageType") == "Collection" and pkg.get("name", "").lower() == "ieeg"
        ]

        if not ieeg_nodes:
            LOG.warning("No ieeg collection found for %s", name)
            return []

        dataset_downloads: List[Dict[str, str]] = []
        for ieeg_node in ieeg_nodes:
            for container, include_container_name in self._containers_for_ieeg(ieeg_node, children):
                file_node = self._select_mef_for_container(container, children)
                if not file_node:
                    LOG.warning(
                        "No MEF files found in %s/%s",
                        name,
                        container.get("name", "ieeg"),
                    )
                    continue

                dest = self._build_destination_path(
                    dataset_name=name,
                    container_name=container.get("name"),
                    file_name=file_node.get("name", "file.mef"),
                    include_container=include_container_name,
                )
                if dest.exists() and not self.overwrite:
                    LOG.info("Skipping existing file %s", dest)
                    dataset_downloads.append(
                        {"dataset": name, "container": container.get("name"), "path": str(dest)}
                    )
                    continue

                download_url = self._get_download_url(file_node["nodeId"])
                self._download_file(download_url, dest)
                dataset_downloads.append(
                    {"dataset": name, "container": container.get("name"), "path": str(dest)}
                )

        return dataset_downloads

    def _load_packages(self, dataset: Dict) -> List[Dict]:
        dataset_id = dataset["content"]["id"]
        name = dataset_name(dataset)
        cache_key = f"package_{name}"
        cached_packages = None if self.refresh_cache else helpers.load_data(cache_key)
        if cached_packages is None:
            LOG.info("Fetching packages for %s", name)
            cached_packages = helpers.get_dataset_packages(dataset_id)
            helpers.save_data(cached_packages, cache_key)
        return cached_packages

    def _build_package_maps(
        self, packages: List[Dict]
    ) -> Tuple[Dict[int, Dict], Dict[Optional[int], List[Dict]]]:
        id_map: Dict[int, Dict] = {}
        children: Dict[Optional[int], List[Dict]] = defaultdict(list)

        for pkg in packages:
            content = pkg.get("content", {})
            pkg_id = content.get("id")
            if pkg_id is None:
                continue
            id_map[pkg_id] = content
            children[content.get("parentId")].append(content)

        for child_list in children.values():
            child_list.sort(key=lambda item: item.get("name", "").lower())

        return id_map, children

    def _containers_for_ieeg(
        self, ieeg_node: Dict, children: Dict[Optional[int], List[Dict]]
    ) -> List[Tuple[Dict, bool]]:
        d_containers = [
            child
            for child in children.get(ieeg_node.get("id"), [])
            if child.get("packageType") == "Collection" and D_FOLDER_PATTERN.match(child.get("name", ""))
        ]
        if d_containers:
            return [(child, True) for child in d_containers]
        return [(ieeg_node, False)]

    def _select_mef_for_container(
        self,
        container: Dict,
        children: Dict[Optional[int], List[Dict]],
    ) -> Optional[Dict]:
        queue: Deque[Dict] = deque(children.get(container.get("id"), []))
        while queue:
            node = queue.popleft()
            if node.get("packageType") == "Collection":
                queue.extend(children.get(node.get("id"), []))
                continue
            if str(node.get("name", "")).lower().endswith(MEF_SUFFIX):
                return node
        return None

    def _build_destination_path(
        self,
        dataset_name: str,
        container_name: Optional[str],
        file_name: str,
        include_container: bool,
    ) -> Path:
        relative = Path(dataset_name)
        if include_container and container_name:
            relative = relative / container_name
        dest = self.output_dir / relative / file_name
        dest.parent.mkdir(parents=True, exist_ok=True)
        return dest

    def _get_download_url(self, node_id: str) -> str:
        manifest_url = f"{helpers.BASE_URL}/packages/download-manifest"
        payload = {"nodeIds": [node_id]}
        resp = self.session.post(
            f"{manifest_url}?api_key={helpers.API_KEY}",
            json=payload,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json().get("data", [])
        if not data:
            raise RuntimeError(f"No download URL returned for {node_id}")
        return data[0]["url"]

    def _download_file(self, url: str, dest: Path) -> None:
        LOG.info("Downloading %s", dest)
        with self.session.get(url, stream=True, timeout=self.timeout) as resp:
            resp.raise_for_status()
            with dest.open("wb") as fh:
                for chunk in resp.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        fh.write(chunk)


def dataset_name(dataset: Dict) -> str:
    return dataset.get("content", {}).get("name", "unknown")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download one MEF file per PennEPI dataset (and D0X folder)."
    )
    parser.add_argument(
        "--output-dir",
        default="mef_samples",
        help="Directory where files will be stored (default: %(default)s)",
    )
    parser.add_argument(
        "--dataset",
        action="append",
        dest="datasets",
        help="Limit execution to specific dataset name(s). Can be passed multiple times.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Process only the first N matching datasets.",
    )
    parser.add_argument(
        "--refresh-cache",
        action="store_true",
        help="Ignore cached dataset/package metadata and refetch from Pennsieve.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Redownload files even if they already exist locally.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="HTTP timeout (seconds) for Pennsieve requests.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level), format="%(message)s")
    output_dir = Path(args.output_dir).expanduser().resolve()

    downloader = PennEpiMefDownloader(
        output_dir=output_dir,
        datasets_filter=args.datasets,
        limit=args.limit,
        refresh_cache=args.refresh_cache,
        overwrite=args.overwrite,
        request_timeout=args.timeout,
    )
    downloader.run()


if __name__ == "__main__":
    main()
