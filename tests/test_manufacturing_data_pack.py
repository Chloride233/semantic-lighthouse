"""Tests for Phase 19.1 manufacturing data pack contract and validation.

Covers:
  - tiny preset generates 13 tables + manifest.json
  - Validator PASS on well-formed data
  - Validator detects: missing table, PK duplicate, FK broken
"""

from __future__ import annotations

import csv
import json
import shutil
import tempfile
from pathlib import Path

# ── Helpers ────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parents[1]
GENERATOR = REPO_ROOT / "scripts" / "generate_manufacturing_dataset.py"
VALIDATOR = REPO_ROOT / "scripts" / "validate_manufacturing_data_pack.py"


def run_generator(output_dir: Path, preset: str = "tiny",
                  seed: int = 42) -> None:
    """Run the data generator as a subprocess."""
    import subprocess
    import sys
    result = subprocess.run(
        [
            sys.executable, str(GENERATOR),
            "--preset", preset,
            "--seed", str(seed),
            "--output-dir", str(output_dir),
        ],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, (
        f"Generator failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )


def run_validator(data_dir: Path) -> tuple[int, str]:
    """Run the validator as a subprocess. Returns (exit_code, output)."""
    import subprocess
    import sys
    result = subprocess.run(
        [sys.executable, str(VALIDATOR), str(data_dir)],
        capture_output=True, text=True, timeout=15,
    )
    return result.returncode, result.stdout


def load_manifest(data_dir: Path) -> dict:
    """Load and return manifest.json from a data pack directory."""
    return json.loads((data_dir / "manifest.json").read_text(encoding="utf-8"))


def count_csv_rows(data_dir: Path, table_name: str) -> int:
    """Count rows (excluding header) in a CSV file."""
    csv_path = data_dir / f"{table_name}.csv"
    if not csv_path.is_file():
        return 0
    with open(csv_path, "r", newline="", encoding="utf-8") as f:
        return sum(1 for _ in f) - 1  # subtract header


def _copy_and_corrupt(src_dir: Path, dest_dir: Path,
                      corrupt_action: str = "remove_table") -> str | None:
    """Copy a valid data pack and apply a corruption. Returns corruption info."""
    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    shutil.copytree(src_dir, dest_dir)

    if corrupt_action == "remove_table":
        # Remove a CSV file
        (dest_dir / "suppliers.csv").unlink()
        return "suppliers.csv"

    elif corrupt_action == "duplicate_pk":
        # Duplicate the first row in materials.csv PK
        csv_path = dest_dir / "materials.csv"
        rows = []
        with open(csv_path, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            for row in reader:
                rows.append(row)
        if len(rows) >= 2:
            # Duplicate the second row's PK onto the first
            rows[0]["material_id"] = rows[1]["material_id"]
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
        return "materials.material_id"

    elif corrupt_action == "broken_fk":
        # Remove a referenced supplier so that materials FK breaks
        csv_path = dest_dir / "suppliers.csv"
        rows = []
        with open(csv_path, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            for row in reader:
                rows.append(row)
        # Keep only the last supplier; materials reference other suppliers
        if len(rows) > 1:
            kept = rows[-1:]
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(kept)
        return "suppliers (truncated for FK break)"

    return None


# ── Tests ──────────────────────────────────────────────────────────────────


class TestManufacturingDataPackGeneration:
    """Verify the generator produces a contract-compliant data pack."""

    def test_tiny_preset_generates_13_tables_and_manifest(self):
        """tiny preset must generate all 13 CSV files + manifest.json +
        metadata.json."""
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "data"
            run_generator(out, preset="tiny", seed=42)

            # 13 CSVs + manifest + metadata = 15 files
            files = sorted(p.name for p in out.iterdir() if p.is_file())
            assert "manifest.json" in files, f"Missing manifest.json in {files}"
            assert "metadata.json" in files, f"Missing metadata.json in {files}"

            expected_csvs = [
                "suppliers.csv", "materials.csv", "products.csv",
                "work_centers.csv", "bills_of_materials.csv",
                "routings.csv", "routing_operations.csv",
                "equipment.csv", "equipment_maintenance.csv",
                "work_orders.csv", "work_order_operations.csv",
                "inventory.csv", "quality_inspections.csv",
            ]
            for csv_name in expected_csvs:
                assert csv_name in files, f"Missing {csv_name}"

            # Load manifest and check structure
            manifest = load_manifest(out)
            assert manifest["manifest_version"] == "1.0"
            assert manifest["data_pack"] == "manufacturing"
            assert manifest["generator"]["name"] == "generate_manufacturing_dataset.py"
            assert manifest["seed"] == 42
            assert manifest["table_count"] == 13
            assert "tables" in manifest
            assert isinstance(manifest["tables"], list)
            assert len(manifest["tables"]) == 13

            # Each table entry has required fields
            required_fields = [
                "table_name", "csv_file", "row_count", "primary_key",
                "foreign_keys", "core_pilot", "business_meaning",
            ]
            for t in manifest["tables"]:
                for rf in required_fields:
                    assert rf in t, (
                        f"Table {t.get('table_name', '?')} missing '{rf}'"
                    )
                # Row count > 0 for tiny preset
                assert t["row_count"] > 0, (
                    f"Table {t['table_name']} has row_count=0"
                )

            # Row counts match CSV
            for t in manifest["tables"]:
                actual = count_csv_rows(out, t["table_name"])
                assert actual == t["row_count"], (
                    f"Table {t['table_name']}: manifest row_count="
                    f"{t['row_count']} but CSV has {actual} rows"
                )

            # core_pilot tables exist (at least 4)
            core = [t for t in manifest["tables"] if t["core_pilot"]]
            assert len(core) >= 4, f"Only {len(core)} core_pilot tables"

            # Known core tables present
            core_names = {t["table_name"] for t in core}
            assert "work_orders" in core_names
            assert "products" in core_names
            assert "equipment" in core_names

    def test_seed_reproducibility(self):
        """Same seed + same preset -> identical data."""
        with tempfile.TemporaryDirectory() as tmp:
            out1 = Path(tmp) / "run1"
            out2 = Path(tmp) / "run2"
            run_generator(out1, preset="tiny", seed=42)
            run_generator(out2, preset="tiny", seed=42)

            # Compare CSV content
            for csv_name in sorted(p.name for p in out1.iterdir()
                                   if p.suffix == ".csv"):
                c1 = (out1 / csv_name).read_text(encoding="utf-8")
                c2 = (out2 / csv_name).read_text(encoding="utf-8")
                assert c1 == c2, f"{csv_name} differs between runs"


class TestManufacturingDataPackValidator:
    """Verify the validator correctly reports PASS and detects defects."""

    def test_validator_pass_on_clean_data(self):
        """Validator reports PASS on a correctly generated data pack."""
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "data"
            run_generator(out, preset="tiny", seed=42)

            exit_code, output = run_validator(out)
            assert exit_code == 0, (
                f"Validator should PASS (exit 0), got {exit_code}\n{output}"
            )
            assert "Result: PASS" in output, (
                f"Expected 'Result: PASS' in output:\n{output}"
            )

    def test_validator_detects_missing_table(self):
        """Validator FAILs when a required CSV is missing."""
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "data"
            run_generator(out, preset="tiny", seed=42)
            broken = Path(tmp) / "broken"
            _copy_and_corrupt(out, broken, "remove_table")

            exit_code, output = run_validator(broken)
            assert exit_code == 1, (
                f"Validator should FAIL (exit 1) for missing table, "
                f"got {exit_code}\n{output}"
            )
            assert "Result: FAIL" in output
            assert "suppliers.csv" in output

    def test_validator_detects_pk_duplicate(self):
        """Validator FAILs when a primary key has duplicate values."""
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "data"
            run_generator(out, preset="tiny", seed=42)
            broken = Path(tmp) / "broken_pk"
            _copy_and_corrupt(out, broken, "duplicate_pk")

            exit_code, output = run_validator(broken)
            assert exit_code == 1, (
                f"Validator should FAIL (exit 1) for duplicate PK, "
                f"got {exit_code}\n{output}"
            )
            assert "Result: FAIL" in output
            assert "duplicate" in output.lower()

    def test_validator_detects_broken_fk(self):
        """Validator FAILs when a foreign key references a non-existent row."""
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "data"
            run_generator(out, preset="tiny", seed=42)
            broken = Path(tmp) / "broken_fk"
            _copy_and_corrupt(out, broken, "broken_fk")

            exit_code, output = run_validator(broken)
            assert exit_code == 1, (
                f"Validator should FAIL (exit 1) for broken FK, "
                f"got {exit_code}\n{output}"
            )
            assert "Result: FAIL" in output
            assert "FK" in output


# ── Smoke helpers ───────────────────────────────────────────────────────

SMOKE_SCRIPT = REPO_ROOT / "scripts" / "smoke_fde_demo.py"


def run_smoke(data_pack: Path | None = None) -> tuple[int, str]:
    """Run the FDE smoke script as a subprocess. Returns (exit_code, stdout)."""
    import subprocess
    import sys
    cmd = [sys.executable, str(SMOKE_SCRIPT)]
    if data_pack is not None:
        cmd.extend(["--data-pack", str(data_pack)])
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=60,
        env={**__import__("os").environ,
             "EMBEDDING_PROVIDER": "fake",
             "CHAT_PROVIDER": "fake"},
    )
    return result.returncode, result.stdout


class TestFDESmokeDataPack:
    """Verify the FDE smoke script correctly reads the data pack manifest."""

    def test_smoke_reads_manifest_and_shows_summary(self):
        """Smoke with --data-pack prints manifest summary and PASSes."""
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "data"
            run_generator(out, preset="tiny", seed=42)

            exit_code, output = run_smoke(out)
            assert exit_code == 0, (
                f"Smoke should PASS (exit 0), got {exit_code}\n{output}"
            )
            # Manifest summary must appear
            assert "Data pack: provided:" in output, (
                f"Expected 'Data pack: provided:' in output:\n{output}"
            )
            assert "manifest_version:" in output
            assert "data_pack:" in output
            assert "preset/seed:" in output
            assert "table_count:" in output
            assert "core_pilot_count:" in output
            assert "total_rows:" in output
            assert "core_pilot:" in output
            # Specific values
            assert "table_count:      13" in output
            assert "core_pilot_count: 8" in output
            assert "total_rows:       279" in output
            assert "seed=42" in output
            # Smoke steps still pass
            assert "FDE Demo Smoke: PASS" in output
            assert "Steps: 11  Passed: 11  Failed: 0" in output

    def test_smoke_missing_manifest_fails_clearly(self):
        """Smoke with a nonexistent data pack directory exits 1 with clear
        error."""
        exit_code, output = run_smoke(Path(".tmp/smoke-nonexistent-xyz"))
        assert exit_code == 1, (
            f"Smoke should FAIL (exit 1) for missing manifest, "
            f"got {exit_code}\n{output}"
        )
        assert "manifest.json not found" in output

    def test_smoke_no_data_pack_flag_stable(self):
        """Smoke without --data-pack auto-generates and still PASSes."""
        exit_code, output = run_smoke(data_pack=None)
        assert exit_code == 0, (
            f"Smoke should PASS (exit 0) without data pack, "
            f"got {exit_code}\n{output}"
        )
        assert "auto-generated default" in output, (
            f"Expected auto-generation note in output:\n{output}"
        )
        assert "FDE Demo Smoke: PASS" in output

    def test_smoke_corrupt_manifest_fails_clearly(self):
        """Smoke with a broken manifest (deleted CSV) exits 1."""
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "data"
            run_generator(out, preset="tiny", seed=42)
            # Delete a CSV that's referenced in manifest
            (out / "work_orders.csv").unlink()

            exit_code, output = run_smoke(out)
            assert exit_code == 1, (
                f"Smoke should FAIL (exit 1) for missing CSV, "
                f"got {exit_code}\n{output}"
            )
            assert "Missing CSV" in output or "FAIL" in output
