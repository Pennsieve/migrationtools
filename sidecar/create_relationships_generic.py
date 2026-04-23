#!/usr/bin/env python3
"""
Generic Create Relationships Script

Creates relationships between records across two models that share a key
property value. For each configured job, paginates records on both sides,
intersects the key values, and posts relationships in bulk.

A local cache file per (dataset, source_model, target_model, rel_type) tracks
key values that have already been linked so re-runs skip them. Cache is
authoritative only for relationships created by this script; relationships
created elsewhere will not be deduplicated.

Config file format (JSON array of jobs):
  [
    {
      "dataset": "PennEPI00214",
      "source_model": "Person",
      "target_model": "ConditionOccurrence",
      "source_key": "CDE_id",
      "target_key": "CDE_id",
      "relationship_type": "HAS_CONDITION"
    }
  ]

Usage:
  python create_relationships_generic.py --api-key KEY --api-secret SECRET \\
      --config relationships.json [--dry-run] [--force-reload] [--verbose]
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote

import requests

from helpers import load_data, save_data, CACHE_DIR
from model_populator import (
    AuthenticationClient,
    get_all_datasets,
    find_dataset_by_name,
)

API2_BASE_URL = "https://api2.pennsieve.io"
RECORD_PAGE_SIZE = 100
RELATIONSHIP_CHUNK_SIZE = 500


def vlog(verbose: bool, *args):
    if verbose:
        print("  [v]", *args)


def _truncate(obj, limit: int = 600) -> str:
    s = json.dumps(obj, default=str)
    return s if len(s) <= limit else s[:limit] + f"... <+{len(s) - limit} chars>"


def get_models_metadata(
    auth_client: AuthenticationClient, dataset_id: str, verbose: bool = False
) -> Dict[str, Dict]:
    """
    Fetch the full metadata for each model in the dataset.
    Returns a map of model-name (and display name) -> {
        id, name, display_name, key_fields (list of x-pennsieve-key property
        names, in schema declaration order), properties (property name list)
    }
    """
    encoded = quote(dataset_id, safe="")
    url = f"{API2_BASE_URL}/metadata/models?dataset_id={encoded}"
    vlog(verbose, f"GET {url}")
    response = requests.get(url, headers=auth_client.get_auth_headers())
    vlog(verbose, f"  -> {response.status_code}")
    response.raise_for_status()
    body = response.json()

    out: Dict[str, Dict] = {}
    for item in body:
        model = item.get("model", {})
        name = model.get("name")
        display = model.get("display_name") or model.get("displayName")
        mid = model.get("id")
        schema = (model.get("latest_version") or {}).get("schema") or {}
        props = schema.get("properties") or {}
        key_fields = [
            pname for pname, pdef in props.items()
            if isinstance(pdef, dict) and pdef.get("x-pennsieve-key")
        ]
        meta = {
            "id": mid,
            "name": name,
            "display_name": display,
            "key_fields": key_fields,
            "properties": list(props.keys()),
        }
        if name:
            out[name] = meta
        if display and display not in out:
            out[display] = meta
    return out


def get_all_model_ids(
    auth_client: AuthenticationClient, dataset_id: str, verbose: bool = False
) -> Dict[str, str]:
    """Return a map of model name -> model ID for the dataset."""
    encoded = quote(dataset_id, safe="")
    url = f"{API2_BASE_URL}/metadata/models?dataset_id={encoded}"
    vlog(verbose, f"GET {url}")
    response = requests.get(url, headers=auth_client.get_auth_headers())
    vlog(verbose, f"  -> {response.status_code}")
    response.raise_for_status()

    body = response.json()
    vlog(verbose, f"  models response type={type(body).__name__} "
                  f"len={len(body) if hasattr(body, '__len__') else 'n/a'}")
    if verbose and isinstance(body, list) and body:
        vlog(verbose, f"  first model item keys: {list(body[0].keys())}")
        vlog(verbose, f"  first model sample: {_truncate(body[0])}")

    models = {}
    skipped = 0
    for item in body:
        model = item.get("model", {})
        name = model.get("name")
        display = model.get("display_name") or model.get("displayName")
        mid = model.get("id")
        if mid and name:
            models[name] = mid
        if mid and display and display not in models:
            models[display] = mid
        if not mid or (not name and not display):
            skipped += 1
    if skipped:
        vlog(verbose, f"  skipped {skipped} model entries with missing name/id")
    return models


def extract_property(record: Dict, prop_name: str, verbose: bool = False,
                     _debug_once: List[bool] = [True]):
    """
    Pull a property value from a record, tolerating both response shapes
    Pennsieve returns: a flat dict {name: value} or a list [{name, value}].
    Returns None if not present. On the first record (per process), logs which
    shape it matched so first-run debugging is fast.
    """
    props = record.get("value") or record.get("values") or record.get("properties")
    source = None
    val = None
    if isinstance(props, dict):
        source = "values/properties dict"
        val = props.get(prop_name)
    elif isinstance(props, list):
        source = "values/properties list-of-{name,value}"
        for entry in props:
            if isinstance(entry, dict) and entry.get("name") == prop_name:
                val = entry.get("value")
                break
    if val is None and prop_name in record:
        source = "top-level record field"
        val = record.get(prop_name)

    if verbose and _debug_once[0]:
        _debug_once[0] = False
        print(f"  [v] extract_property probe: record top-level keys="
              f"{list(record.keys())}")
        print(f"  [v] extract_property probe: matched via {source!r} "
              f"for prop '{prop_name}' -> {val!r}")
    return val


def paginate_records(
    auth_client: AuthenticationClient,
    dataset_id: str,
    model_id: str,
    verbose: bool = False,
) -> List[Dict]:
    """Fetch all records for a model via cursor pagination."""
    encoded = quote(dataset_id, safe="")
    base = (
        f"{API2_BASE_URL}/metadata/models/{model_id}/records/search"
        f"?dataset_id={encoded}&page_size={RECORD_PAGE_SIZE}"
    )

    all_records: List[Dict] = []
    cursor = None
    page = 0
    while True:
        url = f"{base}&cursor={cursor}" if cursor else base
        vlog(verbose, f"POST {url}")
        response = requests.post(
            url, json={}, headers=auth_client.get_auth_headers()
        )
        vlog(verbose, f"  -> {response.status_code}")
        if not response.ok:
            print(f"  ERROR search: {response.status_code} "
                  f"body={response.text[:500]}")
            response.raise_for_status()
        data = response.json()

        if verbose and page == 0:
            vlog(verbose, f"  first page top-level keys: {list(data.keys())}")
            records_preview = data.get("records", [])
            if records_preview:
                vlog(verbose, f"  first record sample: {_truncate(records_preview[0])}")
            else:
                vlog(verbose, f"  first page had 0 records; body: {_truncate(data)}")

        records = data.get("records", [])
        all_records.extend(records)
        vlog(verbose, f"  page {page}: +{len(records)} records "
                      f"(total so far {len(all_records)})")

        cursor = data.get("cursor")
        if not cursor:
            break
        page += 1

    return all_records


def collect_key_map(
    records: List[Dict], key_name: str, verbose: bool = False
) -> Dict[str, List[str]]:
    """Group record IDs by the value of `key_name`. Missing/None keys skipped."""
    by_key: Dict[str, List[str]] = {}
    missing = 0
    for rec in records:
        val = extract_property(rec, key_name, verbose=verbose)
        if val is None or val == "":
            missing += 1
            continue
        by_key.setdefault(str(val), []).append(rec.get("id", ""))
    if verbose:
        vlog(verbose, f"collect_key_map('{key_name}'): "
                      f"{len(by_key)} unique keys, {missing}/{len(records)} "
                      f"records had no value for '{key_name}'")
        if missing == len(records) and records:
            vlog(verbose, f"  WARNING: 0 records had '{key_name}' — "
                          f"property name or response shape likely wrong")
    return by_key


def cache_name(
    dataset: str, source_model: str, target_model: str, rel_type: str
) -> str:
    safe = lambda s: s.replace("/", "_").replace(" ", "_")
    return f"rel_{safe(dataset)}_{safe(source_model)}_{safe(target_model)}_{safe(rel_type)}"


def post_relationships_bulk(
    auth_client: AuthenticationClient,
    dataset_id: str,
    source_model_id: str,
    target_model_id: str,
    record_relationships: List[Dict],
    dry_run: bool,
    verbose: bool,
) -> bool:
    """POST a batch to the bulk relationships endpoint."""
    encoded = quote(dataset_id, safe="")
    url = f"{API2_BASE_URL}/metadata/relationships?dataset_id={encoded}"
    payload = {
        "source_model_id": source_model_id,
        "target_model_id": target_model_id,
        "record_relationships": record_relationships,
    }

    if verbose:
        print(f"      POST {url}")
        print(f"      Payload ({len(record_relationships)} pairs): "
              f"{_truncate(payload, 800)}")
        if record_relationships:
            print(f"      First pair: {json.dumps(record_relationships[0])}")

    if dry_run:
        print(f"      [DRY-RUN] Would POST {len(record_relationships)} relationships")
        return True

    response = requests.post(
        url, json=payload, headers=auth_client.get_auth_headers()
    )
    if verbose:
        print(f"      -> {response.status_code}")
        body_preview = response.text[:500] if response.text else "<empty>"
        print(f"      response body: {body_preview}")
    if response.ok:
        print(f"      Posted {len(record_relationships)} relationships")
        return True
    print(f"      ERROR: {response.status_code} - {response.text}")
    return False


def list_models_probe(
    auth_client: AuthenticationClient,
    dataset_name: str,
    all_datasets: List[Dict],
    verbose: bool,
) -> int:
    """Print every model in the dataset with its property names. Exit code."""
    dataset = find_dataset_by_name(dataset_name, all_datasets)
    if not dataset:
        print(f"ERROR: Dataset not found: {dataset_name}")
        print(f"Tip: check spelling. First 10 available: "
              f"{[d.get('content',{}).get('name') for d in all_datasets[:10]]}")
        return 2
    dataset_id = dataset.get("content", {}).get("id")
    print(f"\nDataset: {dataset_name}  (id={dataset_id})\n")

    encoded = quote(dataset_id, safe="")
    url = f"{API2_BASE_URL}/metadata/models?dataset_id={encoded}"
    vlog(verbose, f"GET {url}")
    response = requests.get(url, headers=auth_client.get_auth_headers())
    response.raise_for_status()
    items = response.json()

    for item in items:
        model = item.get("model", {})
        name = model.get("name")
        mid = model.get("id")
        display = model.get("display_name") or model.get("displayName") or ""
        schema = (model.get("latest_version") or {}).get("schema") or {}
        schema_props = schema.get("properties") or {}
        required = set(schema.get("required") or [])
        print(f"- {name}  (display={display!r}, id={mid})")
        if not schema_props:
            # Fall back to older shape if ever present
            fallback = item.get("properties") or model.get("properties") or []
            if not fallback:
                print(f"    (no properties found; raw model keys: "
                      f"{list(model.keys())})")
                if verbose:
                    print(f"    raw item: {_truncate(item, 800)}")
                continue
            for p in fallback:
                pname = p.get("name") if isinstance(p, dict) else str(p)
                print(f"    - {pname}")
            continue
        for pname, pdef in schema_props.items():
            title = pdef.get("title") if isinstance(pdef, dict) else ""
            is_key = bool(isinstance(pdef, dict) and pdef.get("x-pennsieve-key"))
            is_req = pname in required
            flags = []
            if is_key: flags.append("KEY")
            if is_req: flags.append("required")
            marker = f"  [{', '.join(flags)}]" if flags else ""
            print(f"    - {pname}  (title={title!r}){marker}")
    return 0


def process_job(
    auth_client: AuthenticationClient,
    job: Dict,
    all_datasets: List[Dict],
    force_reload: bool,
    dry_run: bool,
    verbose: bool,
) -> Tuple[int, int]:
    dataset_name = job["dataset"]
    source_model = job["source_model"]
    target_model = job["target_model"]
    # match_on is the single property whose value must be equal on both sides.
    # Legacy fields (shared_key / source_key / target_key) still accepted.
    match_on = job.get("match_on") or job.get("shared_key")
    source_match = job.get("source_match") or job.get("source_key") or match_on
    target_match = job.get("target_match") or job.get("target_key") or match_on
    rel_type = job["relationship_type"]

    if not source_match or not target_match:
        print(f"  ERROR: job missing match_on (or source_match/target_match)")
        return (0, 1)

    print(f"\n{'='*60}")
    print(f"Job: [{dataset_name}] {source_model}.{source_match} "
          f"--[{rel_type}]--> {target_model}.{target_match}")
    print(f"{'='*60}")

    dataset = find_dataset_by_name(dataset_name, all_datasets)
    if not dataset:
        print(f"  ERROR: Dataset not found: {dataset_name}")
        return (0, 1)
    dataset_id = dataset.get("content", {}).get("id")
    if not dataset_id:
        print(f"  ERROR: Dataset has no ID")
        return (0, 1)
    print(f"  Dataset ID: {dataset_id}")

    models_meta = get_models_metadata(auth_client, dataset_id, verbose=verbose)
    vlog(verbose, f"models in dataset: "
                  f"{sorted({m['name'] for m in models_meta.values() if m.get('name')})}")
    src_meta = models_meta.get(source_model)
    tgt_meta = models_meta.get(target_model)
    if not src_meta:
        print(f"  ERROR: Source model '{source_model}' not found")
        print(f"         available: {sorted(models_meta.keys())}")
        return (0, 1)
    if not tgt_meta:
        print(f"  ERROR: Target model '{target_model}' not found")
        print(f"         available: {sorted(models_meta.keys())}")
        return (0, 1)
    source_model_id = src_meta["id"]
    target_model_id = tgt_meta["id"]
    src_key_fields = src_meta["key_fields"] or [source_match]
    tgt_key_fields = tgt_meta["key_fields"] or [target_match]
    vlog(verbose, f"source_model_id={source_model_id} "
                  f"key_fields={src_key_fields}")
    vlog(verbose, f"target_model_id={target_model_id} "
                  f"key_fields={tgt_key_fields}")
    if source_match not in src_meta["properties"]:
        print(f"  WARN: match_on '{source_match}' not in source properties "
              f"{src_meta['properties']}")
    if target_match not in tgt_meta["properties"]:
        print(f"  WARN: match_on '{target_match}' not in target properties "
              f"{tgt_meta['properties']}")

    # Paginate both sides (with cache)
    src_cache_key = f"records_{dataset_name}_{source_model}"
    tgt_cache_key = f"records_{dataset_name}_{target_model}"

    src_records = load_data(src_cache_key, force_reload=force_reload)
    if src_records is None:
        print(f"  Fetching {source_model} records...")
        src_records = paginate_records(auth_client, dataset_id,
                                       source_model_id, verbose=verbose)
        save_data(src_records, src_cache_key)
    else:
        vlog(verbose, f"loaded {source_model} records from cache "
                      f"({src_cache_key})")
    print(f"  {source_model}: {len(src_records)} records")

    tgt_records = load_data(tgt_cache_key, force_reload=force_reload)
    if tgt_records is None:
        print(f"  Fetching {target_model} records...")
        tgt_records = paginate_records(auth_client, dataset_id,
                                       target_model_id, verbose=verbose)
        save_data(tgt_records, tgt_cache_key)
    else:
        vlog(verbose, f"loaded {target_model} records from cache "
                      f"({tgt_cache_key})")
    print(f"  {target_model}: {len(tgt_records)} records")

    # Group records by their match value, preserving full key-field dicts
    def group_by_match(records, match_prop, key_fields):
        by_match: Dict[str, List[Dict]] = {}
        missing_match = 0
        missing_key_fields = 0
        for rec in records:
            mval = extract_property(rec, match_prop, verbose=verbose)
            if mval is None or mval == "":
                missing_match += 1
                continue
            key_dict = {}
            for kf in key_fields:
                v = extract_property(rec, kf)
                if v is None:
                    missing_key_fields += 1
                    key_dict = None
                    break
                key_dict[kf] = v
            if key_dict is None:
                continue
            by_match.setdefault(str(mval), []).append(key_dict)
        vlog(verbose, f"  grouped by '{match_prop}': {len(by_match)} unique "
                      f"values, {missing_match} records missing match, "
                      f"{missing_key_fields} records missing a key field")
        return by_match

    src_by_match = group_by_match(src_records, source_match, src_key_fields)
    tgt_by_match = group_by_match(tgt_records, target_match, tgt_key_fields)

    if not src_by_match:
        print(f"  WARN: no {source_model} records had a '{source_match}' value")
    if not tgt_by_match:
        print(f"  WARN: no {target_model} records had a '{target_match}' value")

    # Dedup cache (list of key values already linked by this script)
    cache_key = cache_name(dataset_name, source_model, target_model, rel_type)
    already_linked = set(load_data(cache_key) or [])
    vlog(verbose, f"dedup cache '{cache_key}': {len(already_linked)} keys "
                  f"previously linked")

    # Pair up
    matched = sorted(set(src_by_match) & set(tgt_by_match))
    src_only = sorted(set(src_by_match) - set(tgt_by_match))
    tgt_only = sorted(set(tgt_by_match) - set(src_by_match))

    for k in src_only:
        print(f"    MISSING counterpart in {target_model}: {source_match}={k}")
    for k in tgt_only:
        print(f"    MISSING counterpart in {source_model}: {target_match}={k}")

    to_link = [k for k in matched if k not in already_linked]
    skipped = len(matched) - len(to_link)
    if skipped:
        print(f"  Skipping {skipped} already-linked matches (local cache)")

    if not to_link:
        print(f"  Nothing new to link.")
        return (0, 0)

    # Build record_relationships using the full key-field identity on each side;
    # cross-product when there are duplicate records for the same match value.
    record_relationships: List[Dict] = []
    pairs_per_key: List[int] = []
    for k in to_link:
        src_list = src_by_match[k]
        tgt_list = tgt_by_match[k]
        if len(src_list) > 1 or len(tgt_list) > 1:
            print(f"    DUP {k}: {len(src_list)}x{source_model} "
                  f"× {len(tgt_list)}x{target_model}")
        count = 0
        for src_rec in src_list:
            for tgt_rec in tgt_list:
                record_relationships.append({
                    "source_record": src_rec,
                    "target_record": tgt_rec,
                    "relationship_type": rel_type,
                })
                count += 1
        pairs_per_key.append(count)

    print(f"  Posting {len(record_relationships)} relationships for "
          f"{len(to_link)} unique match values")

    success = 0
    failure = 0
    posted_keys: List[str] = []
    # Chunk pairs; track which keys are fully posted so we can update cache.
    idx = 0
    key_cursor = 0
    while idx < len(record_relationships):
        chunk = record_relationships[idx:idx + RELATIONSHIP_CHUNK_SIZE]
        ok = post_relationships_bulk(
            auth_client, dataset_id, source_model_id, target_model_id,
            chunk, dry_run=dry_run, verbose=verbose,
        )
        if ok:
            success += len(chunk)
            # Determine which keys were fully covered by this chunk
            consumed = len(chunk)
            while key_cursor < len(to_link) and consumed >= pairs_per_key[key_cursor]:
                consumed -= pairs_per_key[key_cursor]
                posted_keys.append(to_link[key_cursor])
                key_cursor += 1
            # Partial key coverage is left for the next iteration
            if consumed > 0:
                pairs_per_key[key_cursor] -= consumed
        else:
            failure += len(chunk)
            break
        idx += RELATIONSHIP_CHUNK_SIZE

    if posted_keys and not dry_run:
        already_linked.update(posted_keys)
        save_data(sorted(already_linked), cache_key)

    return (success, failure)


def main():
    parser = argparse.ArgumentParser(
        description="Create relationships between records by shared key property",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--api-key", required=True)
    parser.add_argument("--api-secret", required=True)
    parser.add_argument("--config", help="JSON config file of jobs")
    parser.add_argument("--list-models", metavar="DATASET",
                        help="Probe: list all models and their property names "
                             "for the given dataset, then exit")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force-reload", action="store_true",
                        help="Bypass cached datasets/records")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    if not args.config and not args.list_models:
        print("ERROR: provide either --config or --list-models")
        sys.exit(2)

    jobs = []
    if args.config:
        jobs = json.loads(Path(args.config).read_text())
        if not isinstance(jobs, list) or not jobs:
            print("ERROR: config must be a non-empty JSON array of jobs")
            sys.exit(2)

    if args.dry_run:
        print("=" * 60)
        print("DRY RUN MODE - No actual changes will be made")
        print("=" * 60)

    print("\nAuthenticating...")
    auth_client = AuthenticationClient()
    auth_client.authenticate(args.api_key, args.api_secret)
    print("Authentication successful")
    if args.verbose:
        token = auth_client.access_token or ""
        print(f"  [v] access_token acquired (len={len(token)})")

    print("\nFetching datasets...")
    all_datasets = load_data("all_datasets", force_reload=args.force_reload)
    if all_datasets is None:
        all_datasets = get_all_datasets(auth_client)
        save_data(all_datasets, "all_datasets")
    else:
        vlog(args.verbose, "loaded datasets from cache (all_datasets.json)")
    print(f"Total datasets available: {len(all_datasets)}")
    if args.verbose and all_datasets:
        sample = all_datasets[0]
        print(f"  [v] sample dataset top-level keys: {list(sample.keys())}")
        print(f"  [v] sample dataset.content keys: "
              f"{list(sample.get('content', {}).keys())}")

    if args.list_models:
        code = list_models_probe(auth_client, args.list_models,
                                 all_datasets, args.verbose)
        sys.exit(code)

    total_success = 0
    total_failures = 0
    for job in jobs:
        s, f = process_job(
            auth_client, job, all_datasets,
            force_reload=args.force_reload,
            dry_run=args.dry_run, verbose=args.verbose,
        )
        total_success += s
        total_failures += f

    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"Jobs: {len(jobs)}")
    print(f"Relationships posted: {total_success}")
    print(f"Failures: {total_failures}")
    if args.dry_run:
        print("\n[DRY-RUN MODE] No actual changes were made")
    if total_failures > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
