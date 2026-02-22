#!/usr/bin/env python3
"""
ChittyApps Bundle Exporter.
Exports Notion databases to local CSV bundles with manifest tracking.

Usage:
    python scripts/export_bundles.py <bundle_key> [--dry-run] [--config path]

Bundles are defined in chittyos-export.yaml. Each bundle maps to one or more
Notion databases that get exported as CSV files under packages/<bundle>/data/.
"""
import argparse
import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

try:
    from notion_client import Client as NotionClient
except ImportError:
    print("notion-client not installed. Run: pip install notion-client", file=sys.stderr)
    sys.exit(1)


def parse_args():
    p = argparse.ArgumentParser(description="Export Notion databases to CSV bundles")
    p.add_argument("bundle", help="Bundle key to export (e.g., 'services', 'deployments')")
    p.add_argument("--config", default="chittyos-export.yaml", help="Path to export config YAML")
    p.add_argument("--dry-run", action="store_true", help="Validate without writing files")
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


def extract_notion_id(url_or_id: str) -> str:
    """Extract database ID from a Notion URL or pass through raw ID."""
    if url_or_id.startswith("TODO:"):
        return None
    # Handle full URLs like https://www.notion.so/workspace/dbid?v=...
    if "notion.so" in url_or_id:
        # Last 32 chars before any query param
        path = url_or_id.split("?")[0]
        raw_id = path.split("/")[-1].split("-")[-1]
        if len(raw_id) == 32:
            return raw_id
    # Raw UUID (with or without dashes)
    clean = url_or_id.replace("-", "")
    if len(clean) == 32:
        return clean
    return url_or_id


def flatten_property(prop: dict) -> str:
    """Flatten a Notion property value to a string for CSV export."""
    prop_type = prop.get("type", "")

    if prop_type == "title":
        return "".join(t.get("plain_text", "") for t in prop.get("title", []))
    elif prop_type == "rich_text":
        return "".join(t.get("plain_text", "") for t in prop.get("rich_text", []))
    elif prop_type == "number":
        val = prop.get("number")
        return str(val) if val is not None else ""
    elif prop_type == "select":
        sel = prop.get("select")
        return sel.get("name", "") if sel else ""
    elif prop_type == "multi_select":
        return ", ".join(s.get("name", "") for s in prop.get("multi_select", []))
    elif prop_type == "date":
        d = prop.get("date")
        if d:
            start = d.get("start", "")
            end = d.get("end", "")
            return f"{start} - {end}" if end else start
        return ""
    elif prop_type == "checkbox":
        return str(prop.get("checkbox", False))
    elif prop_type == "url":
        return prop.get("url", "") or ""
    elif prop_type == "email":
        return prop.get("email", "") or ""
    elif prop_type == "phone_number":
        return prop.get("phone_number", "") or ""
    elif prop_type == "status":
        s = prop.get("status")
        return s.get("name", "") if s else ""
    elif prop_type == "relation":
        return ", ".join(r.get("id", "") for r in prop.get("relation", []))
    elif prop_type == "formula":
        f = prop.get("formula", {})
        f_type = f.get("type", "")
        return str(f.get(f_type, ""))
    elif prop_type == "rollup":
        r = prop.get("rollup", {})
        r_type = r.get("type", "")
        if r_type == "array":
            return str(len(r.get("array", [])))
        return str(r.get(r_type, ""))
    elif prop_type == "created_time":
        return prop.get("created_time", "")
    elif prop_type == "last_edited_time":
        return prop.get("last_edited_time", "")
    elif prop_type == "created_by":
        return prop.get("created_by", {}).get("name", "")
    elif prop_type == "last_edited_by":
        return prop.get("last_edited_by", {}).get("name", "")
    elif prop_type == "people":
        return ", ".join(p.get("name", "") for p in prop.get("people", []))
    elif prop_type == "files":
        return ", ".join(
            f.get("external", {}).get("url", "") or f.get("file", {}).get("url", "")
            for f in prop.get("files", [])
        )
    else:
        return str(prop)


def query_all_pages(notion: NotionClient, database_id: str) -> list:
    """Query all pages from a Notion database, handling pagination."""
    pages = []
    start_cursor = None

    while True:
        kwargs = {"database_id": database_id, "page_size": 100}
        if start_cursor:
            kwargs["start_cursor"] = start_cursor

        response = notion.databases.query(**kwargs)
        pages.extend(response.get("results", []))

        if not response.get("has_more"):
            break
        start_cursor = response.get("next_cursor")

    return pages


def export_database(notion: NotionClient, db_config: dict, output_dir: Path, dry_run: bool) -> dict:
    """Export a single Notion database to CSV. Returns manifest item."""
    db_key = db_config["key"]
    notion_url = db_config.get("notion_url", "")
    db_id = extract_notion_id(notion_url)

    if not db_id:
        print(f"  Skipping '{db_key}': placeholder URL", file=sys.stderr)
        return None

    print(f"  Exporting '{db_key}' (ID: {db_id[:8]}...)")

    # Query all pages
    pages = query_all_pages(notion, db_id)
    print(f"    Fetched {len(pages)} rows")

    if not pages:
        print(f"    No data to export for '{db_key}'")
        return {"db_key": db_key, "output": f"data/{db_key}.csv", "row_count": 0}

    # Extract column headers from first page's properties
    first_props = pages[0].get("properties", {})
    columns = sorted(first_props.keys())

    # Build rows
    rows = []
    for page in pages:
        props = page.get("properties", {})
        row = {}
        for col in columns:
            if col in props:
                row[col] = flatten_property(props[col])
            else:
                row[col] = ""
        # Add page metadata
        row["_notion_id"] = page.get("id", "")
        row["_last_edited"] = page.get("last_edited_time", "")
        rows.append(row)

    all_columns = columns + ["_notion_id", "_last_edited"]

    if dry_run:
        print(f"    [DRY RUN] Would write {len(rows)} rows to data/{db_key}.csv")
    else:
        csv_path = output_dir / "data" / f"{db_key}.csv"
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=all_columns)
            writer.writeheader()
            writer.writerows(rows)
        print(f"    Wrote {len(rows)} rows to {csv_path}")

    return {
        "db_key": db_key,
        "output": f"data/{db_key}.csv",
        "row_count": len(rows),
        "columns": len(all_columns),
    }


def main():
    args = parse_args()
    cfg = load_yaml_config(args.config)
    bundles = cfg.get("export_bundles", {})
    defaults = cfg.get("defaults", {})

    if args.bundle not in bundles:
        print(f"Bundle '{args.bundle}' not found in config", file=sys.stderr)
        print(f"Available bundles: {', '.join(bundles.keys())}")
        sys.exit(1)

    bundle_cfg = bundles[args.bundle]
    output_root = Path(defaults.get("output_root", "packages"))
    output_dir = output_root / args.bundle

    print(f"ChittyApps Bundle Export: {args.bundle}")
    print(f"  Name: {bundle_cfg.get('name', 'unknown')}")
    print(f"  Schema: {bundle_cfg.get('schema_version', '1.0.0')}")
    print(f"  Output: {output_dir}")
    if args.dry_run:
        print("  Mode: DRY RUN")
    print()

    # Initialize Notion client
    notion_token = os.getenv("NOTION_TOKEN")
    if not notion_token:
        print("NOTION_TOKEN environment variable not set", file=sys.stderr)
        sys.exit(1)

    notion = NotionClient(auth=notion_token)

    # Export each database in the bundle
    databases = bundle_cfg.get("databases", [])
    manifest_items = []

    for db_config in databases:
        result = export_database(notion, db_config, output_dir, args.dry_run)
        if result:
            manifest_items.append(result)

    # Write manifest
    manifest = {
        "bundle": args.bundle,
        "name": bundle_cfg.get("name"),
        "schema_version": bundle_cfg.get("schema_version", "1.0.0"),
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "items": manifest_items,
        "audit": {
            "chitty_id": os.getenv("CHITTY_ID", ""),
            "workflow": os.getenv("GITHUB_WORKFLOW", "manual"),
            "actor": os.getenv("GITHUB_ACTOR", "local"),
        },
        "totals": {
            "databases": len(manifest_items),
            "total_rows": sum(i.get("row_count", 0) for i in manifest_items),
        },
    }

    manifest_filename = defaults.get("manifest_filename", "manifest.json")

    if args.dry_run:
        print(f"\n[DRY RUN] Would write manifest to {output_dir / manifest_filename}")
        print(json.dumps(manifest, indent=2))
    else:
        output_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = output_dir / manifest_filename
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)
        print(f"\nManifest written to {manifest_path}")

    print(f"\nExport complete: {manifest['totals']['databases']} databases, {manifest['totals']['total_rows']} total rows")


if __name__ == "__main__":
    main()
