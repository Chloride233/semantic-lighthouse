"""Download e-commerce benchmark datasets for Ontology business-object testing.

Datasets:
  1. Brazilian E-Commerce (Olist)     — 9 tables, ~100K orders, multi-table relational
  2. Retail Rocket                     — user behavior stream (view/addtocart/transaction)
  3. Online Retail (UCI)               — UK online retail transactions, include returns
  4. Instacart Market Basket Analysis  — ~3M orders, aisle/department/product hierarchy

Usage:
  .venv/Scripts/python scripts/download_ecommerce_datasets.py [--data-dir ./data/ecommerce]

Requirements (auto-checked):
  - kagglehub  (pip install kagglehub)
  - requests   (already in project deps)
"""

from __future__ import annotations

import argparse
import shutil
import sys
import zipfile
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = REPO_ROOT / "data" / "ecommerce"

# ── Dataset registry ──────────────────────────────────────────────────────────

DATASETS = {
    "olist": {
        "name": "Brazilian E-Commerce (Olist)",
        "source": "kaggle",
        "identifier": "olistbr/brazilian-ecommerce",
        "description": "100K orders across 9 relational tables: orders, customers, "
        "products, sellers, payments, reviews, geolocation, order_items, "
        "product_category_name_translation.",
        "tables": [
            "olist_orders_dataset.csv",
            "olist_order_items_dataset.csv",
            "olist_order_payments_dataset.csv",
            "olist_order_reviews_dataset.csv",
            "olist_products_dataset.csv",
            "olist_sellers_dataset.csv",
            "olist_customers_dataset.csv",
            "olist_geolocation_dataset.csv",
            "product_category_name_translation.csv",
        ],
    },
    "retail_rocket": {
        "name": "Retail Rocket E-Commerce Behavior",
        "source": "kaggle",
        "identifier": "retailrocket/ecommerce-dataset",
        "description": "~1.4M user behavior events (view/addtocart/transaction) with "
        "timestamps, visitor IDs, and item properties.",
        "tables": [
            "events.csv",
            "item_properties_part1.csv",
            "item_properties_part2.csv",
            "category_tree.csv",
        ],
    },
    "online_retail": {
        "name": "Online Retail (UCI)",
        "source": "uci",
        "url": "https://archive.ics.uci.edu/ml/machine-learning-databases/00352/Online%20Retail.xlsx",
        "description": "~500K UK online retail transactions with returns tracking. "
        "Classic RFM analysis dataset.",
        "tables": ["Online Retail.xlsx"],
    },
    "instacart": {
        "name": "Instacart Market Basket Analysis",
        "source": "kaggle",
        "identifier": "instacart/instacart-market-basket-analysis",
        "description": "~3M grocery orders with product-aisle-department hierarchy. "
        "Orders, products, aisles, departments, and order_products__prior/train.",
        "tables": [
            "orders.csv",
            "products.csv",
            "aisles.csv",
            "departments.csv",
            "order_products__prior.csv",
            "order_products__train.csv",
        ],
    },
}


# ── Download helpers ──────────────────────────────────────────────────────────


def _download_kaggle(identifier: str, target_dir: Path) -> bool:
    """Download a Kaggle dataset via kagglehub (no auth for public datasets)."""
    import kagglehub

    print(f"  kagglehub downloading {identifier} ...")
    downloaded_path = Path(kagglehub.dataset_download(identifier))

    # Kagglehub downloads to a cache dir — copy files to our target
    if not downloaded_path.exists():
        print(f"  ERROR: kagglehub returned nonexistent path: {downloaded_path}")
        return False

    target_dir.mkdir(parents=True, exist_ok=True)
    file_count = 0
    for src in downloaded_path.iterdir():
        if src.is_file():
            dst = target_dir / src.name
            if not dst.exists():
                shutil.copy2(src, dst)
                file_count += 1

    print(f"  -> {file_count} files copied to {target_dir}")
    return file_count > 0


def _download_uci(url: str, target_dir: Path, filename: str) -> bool:
    """Download a file from a direct HTTP URL with progress indicator."""
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / filename

    if target_path.exists():
        print(f"  -> Already exists: {target_path}")
        return True

    print(f"  Downloading {url}")
    response = requests.get(url, stream=True, timeout=120)
    response.raise_for_status()

    total = int(response.headers.get("content-length", 0))
    downloaded = 0
    chunk_size = 8192

    with open(target_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=chunk_size):
            f.write(chunk)
            downloaded += len(chunk)
            if total:
                pct = downloaded * 100 // total
                print(f"\r  {downloaded // 1024} / {total // 1024} KiB ({pct}%)", end="")

    print(f"\n  -> Saved to {target_path}")
    return True


def _unzip_dir(target_dir: Path) -> bool:
    """Unzip all .zip files found in the directory, then remove them."""
    zips = list(target_dir.glob("*.zip"))
    if not zips:
        return True

    for zp in zips:
        print(f"  Unzipping {zp.name} ...")
        with zipfile.ZipFile(zp, "r") as zf:
            zf.extractall(target_dir)
        zp.unlink()
        print(f"  -> Unzipped and removed {zp.name}")

    return True


# ── Main ──────────────────────────────────────────────────────────────────────


def download_all(data_dir: Path, datasets: list[str] | None = None) -> dict[str, bool]:
    """Download specified datasets (or all) and return per-dataset success map."""
    data_dir = data_dir.resolve()
    data_dir.mkdir(parents=True, exist_ok=True)

    results: dict[str, bool] = {}
    to_download = datasets or list(DATASETS.keys())

    for key in to_download:
        ds = DATASETS[key]
        print(f"\n{'=' * 60}")
        print(f"  {ds['name']}")
        print(f"  {ds['description']}")
        print(f"{'=' * 60}")

        target = data_dir / key
        success = False

        try:
            if ds["source"] == "kaggle":
                success = _download_kaggle(ds["identifier"], target)
            elif ds["source"] == "uci":
                success = _download_uci(ds["url"], target, ds["tables"][0])

            if success:
                _unzip_dir(target)
        except requests.RequestException as exc:
            print(f"  HTTP ERROR: {exc}")
            success = False
        except Exception as exc:
            print(f"  ERROR: {type(exc).__name__}: {exc}")
            success = False

        results[key] = success
        status = "OK" if success else "FAILED"
        print(f"\n  [{status}] {ds['name']}")

    return results


def print_summary(results: dict[str, bool]) -> None:
    """Print a summary table."""
    print(f"\n{'=' * 60}")
    print("  SUMMARY")
    print(f"{'=' * 60}")
    ok = sum(1 for v in results.values() if v)
    fail = len(results) - ok
    for key, success in results.items():
        print(f"  {'✓' if success else '✗'} {DATASETS[key]['name']}")
    print(f"\n  {ok} succeeded, {fail} failed")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download e-commerce benchmark datasets"
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="Target directory (default: data/ecommerce)",
    )
    parser.add_argument(
        "--datasets",
        nargs="*",
        choices=list(DATASETS.keys()),
        default=None,
        help="Specific datasets to download (default: all)",
    )
    args = parser.parse_args()

    # Verify kagglehub
    try:
        import kagglehub  # noqa: F401
    except ImportError:
        print("ERROR: kagglehub not installed. Run: pip install kagglehub")
        sys.exit(1)

    print(f"Target directory: {args.data_dir}")
    print(f"Datasets: {args.datasets or 'all'}\n")

    results = download_all(args.data_dir, args.datasets)
    print_summary(results)

    if not all(results.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
