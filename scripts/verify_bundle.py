#!/usr/bin/env python3
"""
Post-export verification for ChittyApps bundles.
Validates exported data, manifest integrity, and ChittyID compliance.
"""
import argparse
import csv
import json
import sys
from pathlib import Path

import yaml


def parse_args():
    p = argparse.ArgumentParser(description="Verify exported bundle integrity")
    p.add_argument("bundle", help="Bundle key to verify (e.g., 'services')")
    p.add_argument("--config", default="chittyos-export.yaml", help="Path to export config YAML")
    return p.parse_args()


def load_yaml_config(path: str) -> dict:
    try:
        with open(path, "r") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Config file not found: {path}", file=sys.stderr)
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"Invalid YAML in {path}: {e}", file=sys.stderr)
        sys.exit(1)


def verify_manifest(manifest_path: Path) -> tuple:
    """Verify manifest file exists and is valid JSON."""
    if not manifest_path.exists():
        print(f"Manifest not found: {manifest_path}", file=sys.stderr)
        return False, {}

    try:
        with open(manifest_path, "r") as f:
            manifest = json.load(f)
        print(f"Manifest loaded: {manifest_path}")
        return True, manifest
    except json.JSONDecodeError as e:
        print(f"Invalid JSON in manifest: {e}", file=sys.stderr)
        return False, {}


def verify_csv_files(manifest: dict, pkg_dir: Path) -> bool:
    """Verify all CSV files referenced in manifest exist and are readable."""
    items = manifest.get("items", [])
    if not items:
        print("No items in manifest", file=sys.stderr)
        return False

    all_valid = True
    for item in items:
        db_key = item.get("db_key", "unknown")
        output_path = item.get("output", "")
        row_count = item.get("row_count", 0)

        csv_path = pkg_dir / output_path
        if not csv_path.exists():
            print(f"CSV file not found: {csv_path}", file=sys.stderr)
            all_valid = False
            continue

        try:
            with open(csv_path, "r") as f:
                reader = csv.reader(f)
                rows = list(reader)
                actual_count = len(rows) - 1  # Exclude header

                if actual_count != row_count:
                    print(f"Row count mismatch for '{db_key}': manifest={row_count}, actual={actual_count}",
                          file=sys.stderr)

                print(f"CSV verified: {db_key} ({actual_count} rows)")
        except Exception as e:
            print(f"Error reading CSV '{csv_path}': {e}", file=sys.stderr)
            all_valid = False

    return all_valid


def verify_chittyid_compliance(manifest: dict) -> bool:
    """Verify ChittyID is present in audit trail."""
    audit = manifest.get("audit", {})
    chitty_id = audit.get("chitty_id")

    if not chitty_id:
        print("No ChittyID in audit trail (optional but recommended)", file=sys.stderr)
        return True  # Warning, not error

    print(f"ChittyID present: {chitty_id}")
    return True


def verify_schema_version(manifest: dict, expected_version: str) -> bool:
    """Verify schema version matches configuration."""
    actual_version = manifest.get("schema_version")

    if not actual_version:
        print("No schema_version in manifest", file=sys.stderr)
        return False

    if actual_version != expected_version:
        print(f"Schema version mismatch: manifest={actual_version}, config={expected_version}",
              file=sys.stderr)
        return False

    print(f"Schema version: {actual_version}")
    return True


def main():
    args = parse_args()

    print("ChittyApps Bundle Verification\n")
    print(f"Bundle: {args.bundle}")
    print(f"Config: {args.config}\n")

    cfg = load_yaml_config(args.config)
    bundles = cfg.get("export_bundles", {})
    defaults = cfg.get("defaults", {})

    if args.bundle not in bundles:
        print(f"Bundle '{args.bundle}' not found in config", file=sys.stderr)
        sys.exit(1)

    bundle_cfg = bundles[args.bundle]
    output_root = defaults.get("output_root", "packages")
    manifest_filename = defaults.get("manifest_filename", "manifest.json")

    pkg_dir = Path(output_root) / args.bundle
    manifest_path = pkg_dir / manifest_filename

    checks_passed = True

    manifest_valid, manifest = verify_manifest(manifest_path)
    checks_passed &= manifest_valid

    if not manifest_valid:
        print("\nCannot continue verification without valid manifest")
        sys.exit(1)

    checks_passed &= verify_csv_files(manifest, pkg_dir)

    expected_version = bundle_cfg.get("schema_version", "1.0.0")
    checks_passed &= verify_schema_version(manifest, expected_version)

    checks_passed &= verify_chittyid_compliance(manifest)

    print("\n" + "=" * 50)
    if checks_passed:
        print("All verification checks passed!")
        print(f"Bundle '{args.bundle}' is ready for deployment.")
        sys.exit(0)
    else:
        print("Some verification checks failed")
        print("Please review the issues above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
