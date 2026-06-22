"""Generate controllable synthetic manufacturing datasets for Ontology testing.

Produces a full relational manufacturing model with 13 entity types, proper FK chains,
realistic state machines, BOM explosion, routing sequences, inventory tracking,
quality inspections, and equipment maintenance.

Usage:
  # Default scale (500 work orders)
  .venv/Scripts/python scripts/generate_manufacturing_dataset.py

  # Presets
  .venv/Scripts/python scripts/generate_manufacturing_dataset.py --preset medium
  .venv/Scripts/python scripts/generate_manufacturing_dataset.py --preset enterprise

  # Custom scale
  .venv/Scripts/python scripts/generate_manufacturing_dataset.py \
      --num-products 200 --num-materials 1000 --num-work-orders 5000

  # Tiny for fast smoke tests
  .venv/Scripts/python scripts/generate_manufacturing_dataset.py --preset tiny

  # Custom output dir
  .venv/Scripts/python scripts/generate_manufacturing_dataset.py \
      --output-dir ./data/manufacturing

Entity Relationship Model
-------------------------
  supplier (1) ──< (N) material
  material (N) ──< (M) product   [via BOM]
  product  (1) ──< (N) routing
  routing  (1) ──< (N) routing_operation
  work_center (1) ──< (N) routing_operation
  product  (1) ──< (N) work_order
  work_order (1) ──< (N) work_order_operation  [routing→instance]
  work_center (1) ──< (N) equipment
  equipment (1) ──< (N) equipment_maintenance
  material (1) ──< (N) inventory
  work_order (1) ──< (N) quality_inspection
  work_order_operation (1) ──< (N) quality_inspection

State Machines
--------------
  WorkOrder: planned → released → in_progress → completed
              (any)  → on_hold | rejected
  Quality:   pending → in_progress → passed | failed | conditional_accept
  Maintenance: scheduled → in_progress → completed
  Equipment: operational | degraded | down

Dependencies: stdlib only (no extra pip installs).
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# ── Configuration defaults ────────────────────────────────────────────────────


class Config:
    """Generator scale controls.  Set via CLI args or presets."""

    def __init__(
        self,
        *,
        seed: int = 42,
        num_suppliers: int = 20,
        num_materials: int = 200,
        num_products: int = 50,
        num_work_centers: int = 10,
        num_equipment_per_wc: int = 3,
        num_work_orders: int = 500,
        max_bom_items: int = 15,
        min_bom_items: int = 3,
        max_routing_ops: int = 8,
        min_routing_ops: int = 3,
        days_of_history: int = 365,
    ):
        self.seed = seed
        self.num_suppliers = num_suppliers
        self.num_materials = num_materials
        self.num_products = num_products
        self.num_work_centers = num_work_centers
        self.num_equipment_per_wc = num_equipment_per_wc
        self.num_work_orders = num_work_orders
        self.max_bom_items = max_bom_items
        self.min_bom_items = min_bom_items
        self.max_routing_ops = max_routing_ops
        self.min_routing_ops = min_routing_ops
        self.days_of_history = days_of_history


# ── Reference data pools ──────────────────────────────────────────────────────

MATERIAL_NAMES = [
    "Cold-Rolled Steel Sheet AISI 1018",
    "Aluminum 6061-T6 Bar Stock",
    "Copper Wire AWG 12",
    "ABS Plastic Pellet Natural",
    "Nylon 6/6 Granulate",
    "Silicon Wafer 300mm",
    "SMD Resistor 10kΩ 0805",
    "MLCC Capacitor 100nF 0603",
    "PCB FR-4 4-Layer",
    "Stainless Steel 304 Tube",
    "Brass Rod C360",
    "Polycarbonate Sheet Clear",
    "Epoxy Adhesive 2-Part",
    "Silicone Sealant RTV",
    "Bearing Ball 6205-2RS",
    "O-Ring NBR 70 Shore",
    "Threaded Insert M6 Brass",
    "Spring Steel Wire Music Wire",
    "Tungsten Carbide Insert Grade K10",
    "PTFE Tape 0.1mm",
    "Solder Paste SAC305",
    "Flux Core Wire 0.8mm",
    "Heat Shrink Tubing 3:1",
    "Cable Tie Nylon 200mm",
    "Terminal Block 12-Position",
    "Relay 24VDC SPDT",
    "Photoelectric Sensor Diffuse",
    "Pneumatic Cylinder 25mm Bore",
    "Hydraulic Oil ISO 46",
    "Cutting Fluid Semi-Synthetic",
    "Die Steel H13 Block",
    "Graphite Electrode EDM",
    "Ceramic Insulator Alumina",
    "Powder Coating RAL 7016",
    "Zinc Plating Solution",
    "Fiberglass Mat 450g/m²",
    "Carbon Fiber Prepreg 3K",
    "Honeycomb Core Nomex",
    "Titanium Ti-6Al-4V Bar",
    "Inconel 718 Round Bar",
]

SUPPLIER_NAMES = [
    "Precision Metals Supply Co.",
    "Global Polymer Industries",
    "Eastern Electronics Components Ltd.",
    "Midwest Fastener & Hardware",
    "Pacific Chemical Solutions",
    "Advanced Ceramics Inc.",
    "Northern Bearing Works",
    "Southern Tool Steel Corp.",
    "West Coast Sensor Tech",
    "Delta Hydraulics & Pneumatics",
    "Prime Alloys International",
    "Standard Industrial Supply",
    "TechCom Electronics Distribution",
    "Atlas Raw Materials Group",
    "Vertex Specialty Chemicals",
    "Omega Precision Parts",
    "Summit Industrial Fasteners",
    "Cascade Composite Materials",
    "Pioneer Metal Fabrication",
    "Horizon Automation Components",
]

PRODUCT_FAMILIES = [
    ("Hydraulic", ["Pump Assembly", "Valve Block", "Cylinder Assembly", "Manifold"]),
    ("Electronic", ["Motor Controller", "Sensor Module", "Power Supply", "Display Panel"]),
    ("Mechanical", ["Gearbox Assembly", "Drive Shaft", "Bearing Housing", "Coupling"]),
    ("Structural", ["Frame Weldment", "Mounting Bracket", "Support Beam", "Base Plate"]),
    ("Aerospace", ["Wing Rib", "Engine Mount", "Landing Gear Strut", "Control Surface"]),
]

WORK_CENTER_TYPES = [
    ("CNC Machining", "CNC-MC", 80.0),
    ("Manual Lathe", "LATHE", 60.0),
    ("Welding Station", "WELD", 75.0),
    ("Assembly Line", "ASM", 50.0),
    ("Quality Inspection", "QC", 65.0),
    ("Surface Treatment", "SURF", 55.0),
    ("PCB Assembly", "PCBA", 90.0),
    ("Test & Calibration", "TEST", 70.0),
    ("EDM Machining", "EDM", 100.0),
    ("Powder Coating", "COAT", 45.0),
    ("Heat Treatment", "HEAT", 85.0),
    ("Laser Cutting", "LASR", 95.0),
]

LOCATIONS = [
    ("Warehouse A", "WH-A"),
    ("Warehouse B", "WH-B"),
    ("Production Floor", "PROD"),
    ("Raw Material Yard", "RAW"),
    ("Finished Goods Store", "FG"),
]

OPERATION_NAMES = [
    "Rough Cut", "Finish Cut", "Drill", "Tap", "Weld",
    "Assemble", "Inspect", "Test", "Deburr", "Polish",
    "Coat", "Heat Treat", "Solder", "Calibrate", "Pack",
    "Sandblast", "Press Fit", "Torque", "Seal", "Label",
]


# ── Generator ─────────────────────────────────────────────────────────────────


class ManufacturingGenerator:
    """Generates a complete synthetic manufacturing dataset."""

    def __init__(self, cfg: Config, output_dir: Path):
        self.cfg = cfg
        self.output_dir = output_dir
        self.rng = random.Random(cfg.seed)

        self._ids: dict[str, int] = {}
        self.now = datetime.now(tz=timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

    # ── Helpers ───────────────────────────────────────────────────────────

    def _next_id(self, prefix: str) -> str:
        self._ids.setdefault(prefix, 0)
        self._ids[prefix] += 1
        return f"{prefix}-{self._ids[prefix]:06d}"

    def _rand_date(self, days_ago: int = 0, span_days: int = 0) -> str:
        max_back = self.now - timedelta(days=max(days_ago, 1))
        if span_days <= 0:
            return max_back.strftime("%Y-%m-%d")
        offset = self.rng.randint(0, min(span_days, days_ago))
        return (self.now - timedelta(days=offset)).strftime("%Y-%m-%d")

    def _rand_datetime(self, days_ago: int = 0) -> str:
        base = self.now - timedelta(days=max(days_ago, 1))
        base = base.replace(
            hour=self.rng.randint(0, 23),
            minute=self.rng.randint(0, 59),
            second=self.rng.randint(0, 59),
        )
        return base.isoformat()

    def _write_csv(self, filename: str, rows: list[dict]) -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        path = self.output_dir / filename
        if not rows:
            return path
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        return path

    # ── Entity generators (each returns list[dict]) ───────────────────────

    def _gen_suppliers(self) -> list[dict]:
        rows = []
        for i in range(self.cfg.num_suppliers):
            rows.append({
                "supplier_id": self._next_id("SUP"),
                "supplier_name": self.rng.choice(SUPPLIER_NAMES),
                "supplier_code": f"S-{i+1:04d}",
                "country": self.rng.choice(
                    ["US", "CN", "DE", "JP", "KR", "TW", "IN", "MX"]
                ),
                "lead_time_days": self.rng.choice([3, 5, 7, 10, 14, 21, 30]),
                "min_order_qty": self.rng.choice([1, 10, 50, 100, 500]),
                "quality_rating": round(self.rng.uniform(2.0, 5.0), 1),
                "is_active": self.rng.choices([True, False], weights=[90, 10])[0],
                "created_at": self._rand_date(
                    self.cfg.days_of_history, self.cfg.days_of_history
                ),
            })
        return rows

    def _gen_materials(self) -> list[dict]:
        rows = []
        units = ["kg", "m", "pcs", "L", "m²", "roll", "tube", "sheet"]
        for i in range(self.cfg.num_materials):
            name = self.rng.choice(MATERIAL_NAMES)
            rows.append({
                "material_id": self._next_id("MAT"),
                "material_name": name,
                "material_code": f"M-{i+1:05d}",
                "supplier_id": None,  # assigned after suppliers generated
                "unit_of_measure": self.rng.choice(units),
                "unit_cost": round(self.rng.uniform(0.05, 500.0), 4),
                "lead_time_days": self.rng.choice([1, 3, 5, 7, 14, 21, 30, 45]),
                "safety_stock_qty": round(self.rng.uniform(0, 1000), 2),
                "reorder_point": round(self.rng.uniform(10, 500), 2),
                "abc_class": self.rng.choices(
                    ["A", "B", "C"], weights=[15, 35, 50]
                )[0],
                "is_batch_tracked": self.rng.choices(
                    [True, False], weights=[40, 60]
                )[0],
            })
        return rows

    def _gen_products(self) -> list[dict]:
        rows = []
        for i in range(self.cfg.num_products):
            family_name, variants = self.rng.choice(PRODUCT_FAMILIES)
            variant = self.rng.choice(variants)
            rows.append({
                "product_id": self._next_id("PRD"),
                "product_name": f"{family_name} {variant}",
                "product_code": f"P-{i+1:04d}",
                "product_family": family_name,
                "revision": chr(65 + self.rng.randint(0, 5)),
                "unit_cost": round(self.rng.uniform(50.0, 50000.0), 2),
                "unit_price": 0.0,
                "lead_time_days": self.rng.choice([1, 2, 3, 5, 7, 10, 14, 21]),
                "min_lot_size": self.rng.choice([1, 5, 10, 20, 50, 100]),
                "is_make_to_order": self.rng.choices(
                    [True, False], weights=[30, 70]
                )[0],
                "created_at": self._rand_date(
                    self.cfg.days_of_history, self.cfg.days_of_history
                ),
            })
        return rows

    def _gen_boms(
        self, products: list[dict], materials: list[dict]
    ) -> list[dict]:
        rows = []
        mat_ids = [m["material_id"] for m in materials]
        for prod in products:
            n = self.rng.randint(self.cfg.min_bom_items, self.cfg.max_bom_items)
            chosen = self.rng.sample(mat_ids, min(n, len(mat_ids)))
            for seq, mat_id in enumerate(chosen, 1):
                rows.append({
                    "bom_id": self._next_id("BOM"),
                    "product_id": prod["product_id"],
                    "material_id": mat_id,
                    "sequence": seq,
                    "quantity_per_unit": round(self.rng.uniform(0.001, 50.0), 3),
                    "scrap_rate_pct": round(self.rng.uniform(0.0, 5.0), 2),
                    "is_critical": self.rng.choices(
                        [True, False], weights=[20, 80]
                    )[0],
                })
        return rows

    def _gen_work_centers(self) -> list[dict]:
        rows = []
        for i in range(self.cfg.num_work_centers):
            wc_type = self.rng.choice(WORK_CENTER_TYPES)
            rows.append({
                "work_center_id": self._next_id("WC"),
                "work_center_name": f"{wc_type[0]} #{i+1}",
                "work_center_code": f"{wc_type[1]}-{i+1:02d}",
                "work_center_type": wc_type[0],
                "hourly_rate": round(wc_type[2] + self.rng.uniform(-10, 20), 2),
                "capacity_hours_per_day": self.rng.choice([8, 16, 24]),
                "setup_time_minutes": self.rng.choice([5, 10, 15, 30, 45, 60]),
                "efficiency_pct": round(self.rng.uniform(75.0, 98.0), 1),
                "is_bottleneck": self.rng.choices(
                    [True, False], weights=[20, 80]
                )[0],
            })
        return rows

    def _gen_routings(
        self, products: list[dict], work_centers: list[dict]
    ) -> tuple[list[dict], list[dict]]:
        routing_rows = []
        op_rows = []
        wc_ids = [w["work_center_id"] for w in work_centers]
        for prod in products:
            routing_id = self._next_id("RTG")
            routing_rows.append({
                "routing_id": routing_id,
                "product_id": prod["product_id"],
                "routing_name": f"Routing for {prod['product_name']}",
                "revision": chr(65 + self.rng.randint(0, 3)),
                "is_active": True,
            })
            n_ops = self.rng.randint(
                self.cfg.min_routing_ops, self.cfg.max_routing_ops
            )
            for seq in range(1, n_ops + 1):
                op_rows.append({
                    "routing_operation_id": self._next_id("ROP"),
                    "routing_id": routing_id,
                    "sequence": seq,
                    "operation_name": self.rng.choice(OPERATION_NAMES),
                    "work_center_id": self.rng.choice(wc_ids),
                    "standard_time_minutes": round(
                        self.rng.uniform(1.0, 120.0), 1
                    ),
                    "setup_time_minutes": round(
                        self.rng.uniform(5.0, 45.0), 1
                    ),
                    "sequence_dependent": self.rng.choices(
                        [True, False], weights=[30, 70]
                    )[0],
                })
        return routing_rows, op_rows

    def _gen_equipment(self, work_centers: list[dict]) -> list[dict]:
        eq_types = {
            "CNC Machining": ["5-Axis Mill", "CNC Lathe", "VMC"],
            "Manual Lathe": ["Engine Lathe", "Turret Lathe"],
            "Welding Station": ["TIG Welder", "MIG Welder", "Spot Welder"],
            "Assembly Line": ["Torque Station", "Press Fit", "Conveyor"],
            "Quality Inspection": ["CMM", "Vision System", "Hardness Tester"],
            "Surface Treatment": ["Sandblaster", "Chemical Bath"],
            "PCB Assembly": ["Pick & Place", "Reflow Oven", "AOI"],
            "Test & Calibration": ["Oscilloscope", "Load Tester"],
            "EDM Machining": ["Wire EDM", "Sinker EDM"],
            "Powder Coating": ["Spray Booth", "Curing Oven"],
            "Heat Treatment": ["Furnace", "Quench Tank"],
            "Laser Cutting": ["Fiber Laser", "CO2 Laser"],
        }
        rows = []
        for wc in work_centers:
            candidates = eq_types.get(wc["work_center_type"], ["General Equipment"])
            for _ in range(self.cfg.num_equipment_per_wc):
                rows.append({
                    "equipment_id": self._next_id("EQP"),
                    "work_center_id": wc["work_center_id"],
                    "equipment_name": self.rng.choice(candidates),
                    "serial_number": f"SN-{self.rng.randint(10000, 99999)}",
                    "install_date": self._rand_date(
                        self.cfg.days_of_history, self.cfg.days_of_history
                    ),
                    "last_calibration": self._rand_date(90, 90),
                    "status": self.rng.choices(
                        ["operational", "operational", "operational", "degraded", "down"],
                        weights=[75, 10, 5, 7, 3],
                    )[0],
                })
        return rows

    def _gen_maintenance(self, equipment: list[dict]) -> list[dict]:
        rows = []
        types = ["preventive", "corrective", "predictive", "calibration", "overhaul"]
        for eq in equipment:
            for _ in range(self.rng.randint(0, 4)):
                mt = self.rng.choice(types)
                rows.append({
                    "maintenance_id": self._next_id("MNT"),
                    "equipment_id": eq["equipment_id"],
                    "maintenance_type": mt,
                    "scheduled_date": self._rand_date(
                        self.cfg.days_of_history, self.cfg.days_of_history
                    ),
                    "completed_date": (
                        self._rand_date(self.cfg.days_of_history, self.cfg.days_of_history)
                        if self.rng.random() > 0.15
                        else None
                    ),
                    "downtime_hours": round(self.rng.uniform(0.5, 48.0), 1),
                    "cost": round(self.rng.uniform(50.0, 5000.0), 2),
                    "technician": f"TECH-{self.rng.randint(1, 30):03d}",
                    "status": self.rng.choices(
                        ["completed", "in_progress", "scheduled"],
                        weights=[70, 15, 15],
                    )[0],
                })
        return rows

    def _gen_work_orders(self, products: list[dict]) -> list[dict]:
        rows = []
        product_ids = [p["product_id"] for p in products]
        states = (
            ["completed"] * 45
            + ["in_progress"] * 20
            + ["released"] * 15
            + ["planned"] * 10
            + ["on_hold"] * 5
            + ["rejected"] * 5
        )
        priorities = ["high"] * 15 + ["medium"] * 60 + ["low"] * 25

        for i in range(self.cfg.num_work_orders):
            state = self.rng.choice(states)
            created = self._rand_datetime(
                self.rng.randint(1, self.cfg.days_of_history)
            )
            qty = self.rng.choice([1, 2, 5, 10, 20, 50, 100, 200, 500])
            completed_qty = (
                self.rng.randint(0, qty) if state == "completed"
                else (self.rng.randint(0, qty) if state == "in_progress" else 0)
            )
            rows.append({
                "work_order_id": self._next_id("WO"),
                "work_order_number": (
                    f"WO-{self.rng.randint(2023, 2026)}-{i+1:05d}"
                ),
                "product_id": self.rng.choice(product_ids),
                "quantity_ordered": qty,
                "quantity_completed": completed_qty,
                "quantity_scrapped": self.rng.randint(0, max(1, qty // 20)),
                "status": state,
                "priority": self.rng.choice(priorities),
                "scheduled_start": created,
                "scheduled_end": self._rand_datetime(
                    max(1, self.cfg.days_of_history - 30)
                ),
                "actual_start": (
                    created if state not in ("planned", "rejected") else None
                ),
                "actual_end": (
                    self._rand_datetime(max(1, self.cfg.days_of_history - 60))
                    if state == "completed" else None
                ),
                "released_by": (
                    f"USER-{self.rng.randint(1, 50):03d}"
                    if state not in ("planned",) else None
                ),
                "rejection_reason": (
                    self.rng.choice([
                        "Design change required",
                        "Material unavailable",
                        "Capacity constraint",
                        "Quality hold",
                        "Customer order cancelled",
                    ]) if state == "rejected" else None
                ),
                "created_at": created,
            })
        return rows

    def _gen_wo_operations(
        self,
        work_orders: list[dict],
        routings: list[dict],
        routing_ops: list[dict],
    ) -> list[dict]:
        rows = []
        prod_to_routing = {
            r["product_id"]: r["routing_id"] for r in routings
        }
        routing_to_ops: dict[str, list[dict]] = {}
        for op in routing_ops:
            routing_to_ops.setdefault(op["routing_id"], []).append(op)

        for wo in work_orders:
            routing_id = prod_to_routing.get(wo["product_id"])
            if not routing_id:
                continue
            ops = routing_to_ops.get(routing_id, [])
            for op_template in ops:
                if wo["status"] == "completed":
                    op_status = "completed"
                elif wo["status"] == "in_progress" and self.rng.random() > 0.5:
                    op_status = "in_progress"
                else:
                    op_status = "pending"

                rows.append({
                    "wo_operation_id": self._next_id("WOP"),
                    "work_order_id": wo["work_order_id"],
                    "routing_operation_id": op_template["routing_operation_id"],
                    "sequence": op_template["sequence"],
                    "work_center_id": op_template["work_center_id"],
                    "status": op_status,
                    "planned_start": wo["scheduled_start"],
                    "planned_end": wo["scheduled_end"],
                    "actual_start": (
                        wo["actual_start"] if op_status != "pending" else None
                    ),
                    "actual_end": (
                        wo["actual_end"] if op_status == "completed" else None
                    ),
                    "setup_time_minutes": op_template["setup_time_minutes"],
                    "run_time_minutes": round(
                        op_template["standard_time_minutes"]
                        * wo["quantity_completed"]
                        * self.rng.uniform(0.9, 1.3),
                        1,
                    ),
                    "operator_id": f"OPR-{self.rng.randint(1, 40):03d}",
                })
        return rows

    def _gen_inventory(self, materials: list[dict]) -> list[dict]:
        rows = []
        for mat in materials:
            for loc_name, loc_code in LOCATIONS:
                rows.append({
                    "inventory_id": self._next_id("INV"),
                    "material_id": mat["material_id"],
                    "location_code": loc_code,
                    "location_name": loc_name,
                    "quantity_on_hand": round(
                        self.rng.uniform(0, 5000), 3
                    ),
                    "quantity_allocated": round(
                        self.rng.uniform(0, 500), 3
                    ),
                    "quantity_on_order": round(
                        self.rng.uniform(0, 1000), 3
                    ),
                    "last_count_date": self._rand_date(30, 30),
                    "last_transaction_date": self._rand_date(7, 7),
                })
        return rows

    def _gen_quality_inspections(
        self,
        work_orders: list[dict],
        wo_operations: list[dict],
    ) -> list[dict]:
        rows = []
        results = ["passed", "passed", "passed", "failed", "conditional_accept"]

        # Final inspections per work order
        for wo in work_orders:
            if wo["status"] in ("planned",):
                continue
            if self.rng.random() > 0.3:
                r = self.rng.choice(results)
                rows.append({
                    "inspection_id": self._next_id("QIN"),
                    "work_order_id": wo["work_order_id"],
                    "wo_operation_id": None,
                    "inspection_type": "final",
                    "inspection_date": (
                        wo.get("actual_end") or wo["scheduled_end"]
                    ),
                    "result": r,
                    "defect_count": (
                        self.rng.randint(1, 10) if r == "failed" else 0
                    ),
                    "measured_value": round(self.rng.uniform(0.5, 100.0), 3),
                    "spec_lower": 1.0,
                    "spec_upper": 99.0,
                    "inspector_id": f"INSP-{self.rng.randint(1, 20):03d}",
                    "notes": "Auto-generated final inspection",
                })

        # In-process inspections per operation
        for wop in wo_operations:
            if wop["status"] not in ("completed", "in_progress"):
                continue
            if self.rng.random() > 0.6:
                r = self.rng.choice(results)
                rows.append({
                    "inspection_id": self._next_id("QIN"),
                    "work_order_id": wop["work_order_id"],
                    "wo_operation_id": wop["wo_operation_id"],
                    "inspection_type": "in_process",
                    "inspection_date": (
                        wop.get("actual_end") or wop["planned_end"]
                    ),
                    "result": r,
                    "defect_count": (
                        self.rng.randint(1, 5) if r == "failed" else 0
                    ),
                    "measured_value": round(self.rng.uniform(0.5, 100.0), 3),
                    "spec_lower": 1.0,
                    "spec_upper": 99.0,
                    "inspector_id": f"INSP-{self.rng.randint(1, 20):03d}",
                    "notes": "In-process check",
                })
        return rows

    # ── Manifest (Phase 19.1 data pack contract) ──────────────────────────

    def _build_manifest(self, counts: dict[str, int]) -> dict:
        """Build a lightweight manifest.json for the data pack contract.

        The manifest is the canonical contract that validators and
        downstream consumers (FDE demo, Ontology pilot) can rely on.
        """
        # Phase 19 core pilot subset: the tables most essential for the
        # equipment-reliability FDE demo narrative.
        CORE_PILOT_TABLES = {
            "suppliers", "materials", "products", "work_centers",
            "work_orders", "work_order_operations", "equipment",
            "quality_inspections",
        }

        TABLE_SPEC: list[dict] = [
            {
                "table_name": "suppliers",
                "csv_file": "suppliers.csv",
                "primary_key": ["supplier_id"],
                "foreign_keys": [],
                "business_meaning": (
                    "Raw material and component suppliers with quality "
                    "ratings, lead times, and active status"
                ),
            },
            {
                "table_name": "materials",
                "csv_file": "materials.csv",
                "primary_key": ["material_id"],
                "foreign_keys": [
                    {
                        "columns": ["supplier_id"],
                        "references": {"table": "suppliers", "columns": ["supplier_id"]},
                    },
                ],
                "business_meaning": (
                    "Raw materials, components, and sub-assemblies with "
                    "unit costs, ABC classification, and batch tracking flags"
                ),
            },
            {
                "table_name": "products",
                "csv_file": "products.csv",
                "primary_key": ["product_id"],
                "foreign_keys": [],
                "business_meaning": (
                    "Finished products organized by product family with "
                    "revisions, costs, lead times, and make-to-order flags"
                ),
            },
            {
                "table_name": "work_centers",
                "csv_file": "work_centers.csv",
                "primary_key": ["work_center_id"],
                "foreign_keys": [],
                "business_meaning": (
                    "Production work centers / lines with hourly rates, "
                    "capacity, efficiency, and bottleneck flags"
                ),
            },
            {
                "table_name": "bills_of_materials",
                "csv_file": "bills_of_materials.csv",
                "primary_key": ["bom_id"],
                "foreign_keys": [
                    {
                        "columns": ["product_id"],
                        "references": {"table": "products", "columns": ["product_id"]},
                    },
                    {
                        "columns": ["material_id"],
                        "references": {"table": "materials", "columns": ["material_id"]},
                    },
                ],
                "business_meaning": (
                    "Bill of Materials: per-product material composition "
                    "with quantities, scrap rates, and criticality flags"
                ),
            },
            {
                "table_name": "routings",
                "csv_file": "routings.csv",
                "primary_key": ["routing_id"],
                "foreign_keys": [
                    {
                        "columns": ["product_id"],
                        "references": {"table": "products", "columns": ["product_id"]},
                    },
                ],
                "business_meaning": (
                    "Manufacturing routings: the production recipe that "
                    "defines the sequence of operations for each product"
                ),
            },
            {
                "table_name": "routing_operations",
                "csv_file": "routing_operations.csv",
                "primary_key": ["routing_operation_id"],
                "foreign_keys": [
                    {
                        "columns": ["routing_id"],
                        "references": {"table": "routings", "columns": ["routing_id"]},
                    },
                    {
                        "columns": ["work_center_id"],
                        "references": {
                            "table": "work_centers",
                            "columns": ["work_center_id"],
                        },
                    },
                ],
                "business_meaning": (
                    "Individual steps within a routing, each assigned to a "
                    "work center with standard and setup times"
                ),
            },
            {
                "table_name": "equipment",
                "csv_file": "equipment.csv",
                "primary_key": ["equipment_id"],
                "foreign_keys": [
                    {
                        "columns": ["work_center_id"],
                        "references": {
                            "table": "work_centers",
                            "columns": ["work_center_id"],
                        },
                    },
                ],
                "business_meaning": (
                    "Physical equipment assets per work center with serial "
                    "numbers, calibration dates, and operational status"
                ),
            },
            {
                "table_name": "equipment_maintenance",
                "csv_file": "equipment_maintenance.csv",
                "primary_key": ["maintenance_id"],
                "foreign_keys": [
                    {
                        "columns": ["equipment_id"],
                        "references": {
                            "table": "equipment",
                            "columns": ["equipment_id"],
                        },
                    },
                ],
                "business_meaning": (
                    "Maintenance records per equipment asset: type, "
                    "downtime, cost, technician, and completion status"
                ),
            },
            {
                "table_name": "work_orders",
                "csv_file": "work_orders.csv",
                "primary_key": ["work_order_id"],
                "foreign_keys": [
                    {
                        "columns": ["product_id"],
                        "references": {"table": "products", "columns": ["product_id"]},
                    },
                ],
                "business_meaning": (
                    "Production work orders with quantities, status state "
                    "machine, priority, scheduling, and rejection reasons"
                ),
            },
            {
                "table_name": "work_order_operations",
                "csv_file": "work_order_operations.csv",
                "primary_key": ["wo_operation_id"],
                "foreign_keys": [
                    {
                        "columns": ["work_order_id"],
                        "references": {
                            "table": "work_orders",
                            "columns": ["work_order_id"],
                        },
                    },
                    {
                        "columns": ["routing_operation_id"],
                        "references": {
                            "table": "routing_operations",
                            "columns": ["routing_operation_id"],
                        },
                    },
                    {
                        "columns": ["work_center_id"],
                        "references": {
                            "table": "work_centers",
                            "columns": ["work_center_id"],
                        },
                    },
                ],
                "business_meaning": (
                    "Per-work-order operation instances: planned vs actual "
                    "timing, run times, operator assignment, and status"
                ),
            },
            {
                "table_name": "inventory",
                "csv_file": "inventory.csv",
                "primary_key": ["inventory_id"],
                "foreign_keys": [
                    {
                        "columns": ["material_id"],
                        "references": {"table": "materials", "columns": ["material_id"]},
                    },
                ],
                "business_meaning": (
                    "Per-location inventory records for materials: "
                    "on-hand, allocated, on-order quantities with count dates"
                ),
            },
            {
                "table_name": "quality_inspections",
                "csv_file": "quality_inspections.csv",
                "primary_key": ["inspection_id"],
                "foreign_keys": [
                    {
                        "columns": ["work_order_id"],
                        "references": {
                            "table": "work_orders",
                            "columns": ["work_order_id"],
                        },
                    },
                    {
                        "columns": ["wo_operation_id"],
                        "references": {
                            "table": "work_order_operations",
                            "columns": ["wo_operation_id"],
                        },
                    },
                ],
                "business_meaning": (
                    "Quality inspection records: final and in-process "
                    "checks with results, defect counts, and spec limits"
                ),
            },
        ]

        tables = []
        for spec in TABLE_SPEC:
            tname = spec["table_name"]
            # Map counts key to table name
            count_key = {
                "bills_of_materials": "bom_items",
                "work_order_operations": "wo_operations",
                "quality_inspections": "quality_inspections",
                "equipment_maintenance": "maintenance",
            }.get(tname, tname)
            row_count = counts.get(count_key, 0)
            tables.append({
                **spec,
                "row_count": row_count,
                "core_pilot": tname in CORE_PILOT_TABLES,
            })

        return {
            "manifest_version": "1.0",
            "data_pack": "manufacturing",
            "generator": {
                "name": "generate_manufacturing_dataset.py",
                "version": "1.0",
            },
            "preset": getattr(self.cfg, "_preset_name", "custom"),
            "seed": self.cfg.seed,
            "generated_at": self.now.isoformat(),
            "table_count": len(tables),
            "total_rows": sum(t["row_count"] for t in tables),
            "core_pilot_table_count": sum(
                1 for t in tables if t["core_pilot"]
            ),
            "tables": tables,
        }

    # ── Orchestration ──────────────────────────────────────────────────────

    def run(self) -> dict[str, int]:
        print(f"Generating manufacturing dataset  seed={self.cfg.seed}")
        print(f"Output: {self.output_dir}")
        print(
            f"Scale: {self.cfg.num_products} products, "
            f"{self.cfg.num_materials} materials, "
            f"{self.cfg.num_work_orders} work orders\n"
        )

        counts: dict[str, int] = {}

        # Phase 1: Independent entities
        suppliers = self._gen_suppliers()
        self._write_csv("suppliers.csv", suppliers)
        counts["suppliers"] = len(suppliers)
        print(f"  [OK] suppliers: {counts['suppliers']}")

        materials = self._gen_materials()
        sup_ids = [s["supplier_id"] for s in suppliers]
        for m in materials:
            m["supplier_id"] = self.rng.choice(sup_ids)
        self._write_csv("materials.csv", materials)
        counts["materials"] = len(materials)
        print(f"  [OK] materials: {counts['materials']}")

        products = self._gen_products()
        self._write_csv("products.csv", products)
        counts["products"] = len(products)
        print(f"  [OK] products: {counts['products']}")

        work_centers = self._gen_work_centers()
        self._write_csv("work_centers.csv", work_centers)
        counts["work_centers"] = len(work_centers)
        print(f"  [OK] work_centers: {counts['work_centers']}")

        # Phase 2: Dependent entities
        boms = self._gen_boms(products, materials)
        self._write_csv("bills_of_materials.csv", boms)
        counts["bom_items"] = len(boms)
        print(f"  [OK] BOM items: {counts['bom_items']}")

        routings, routing_ops = self._gen_routings(products, work_centers)
        self._write_csv("routings.csv", routings)
        self._write_csv("routing_operations.csv", routing_ops)
        counts["routings"] = len(routings)
        counts["routing_operations"] = len(routing_ops)
        print(
            f"  [OK] routings: {counts['routings']}, "
            f"operations: {counts['routing_operations']}"
        )

        equipment = self._gen_equipment(work_centers)
        self._write_csv("equipment.csv", equipment)
        counts["equipment"] = len(equipment)
        print(f"  [OK] equipment: {counts['equipment']}")

        maintenance = self._gen_maintenance(equipment)
        self._write_csv("equipment_maintenance.csv", maintenance)
        counts["maintenance"] = len(maintenance)
        print(f"  [OK] maintenance records: {counts['maintenance']}")

        # Phase 3: Transactional entities
        work_orders = self._gen_work_orders(products)
        self._write_csv("work_orders.csv", work_orders)
        counts["work_orders"] = len(work_orders)
        print(f"  [OK] work orders: {counts['work_orders']}")

        wo_ops = self._gen_wo_operations(work_orders, routings, routing_ops)
        self._write_csv("work_order_operations.csv", wo_ops)
        counts["wo_operations"] = len(wo_ops)
        print(f"  [OK] work order operations: {counts['wo_operations']}")

        # Phase 4: Support entities
        inventory = self._gen_inventory(materials)
        self._write_csv("inventory.csv", inventory)
        counts["inventory"] = len(inventory)
        print(f"  [OK] inventory records: {counts['inventory']}")

        inspections = self._gen_quality_inspections(work_orders, wo_ops)
        self._write_csv("quality_inspections.csv", inspections)
        counts["quality_inspections"] = len(inspections)
        print(f"  [OK] quality inspections: {counts['quality_inspections']}")

        # Metadata (legacy, keep for backward compat)
        metadata = {
            "schema_version": "1.0",
            "generator": "generate_manufacturing_dataset.py",
            "seed": self.cfg.seed,
            "generated_at": self.now.isoformat(),
            "config": {
                "num_suppliers": self.cfg.num_suppliers,
                "num_materials": self.cfg.num_materials,
                "num_products": self.cfg.num_products,
                "num_work_centers": self.cfg.num_work_centers,
                "num_work_orders": self.cfg.num_work_orders,
                "days_of_history": self.cfg.days_of_history,
            },
            "entity_counts": counts,
            "foreign_keys": {
                "materials.supplier_id": "suppliers.supplier_id",
                "bills_of_materials.product_id": "products.product_id",
                "bills_of_materials.material_id": "materials.material_id",
                "routings.product_id": "products.product_id",
                "routing_operations.routing_id": "routings.routing_id",
                "routing_operations.work_center_id": "work_centers.work_center_id",
                "equipment.work_center_id": "work_centers.work_center_id",
                "equipment_maintenance.equipment_id": "equipment.equipment_id",
                "work_orders.product_id": "products.product_id",
                "work_order_operations.work_order_id": "work_orders.work_order_id",
                "work_order_operations.routing_operation_id": (
                    "routing_operations.routing_operation_id"
                ),
                "work_order_operations.work_center_id": "work_centers.work_center_id",
                "inventory.material_id": "materials.material_id",
                "quality_inspections.work_order_id": "work_orders.work_order_id",
                "quality_inspections.wo_operation_id": (
                    "work_order_operations.wo_operation_id"
                ),
            },
            "state_machines": {
                "work_orders.status": [
                    "planned", "released", "in_progress",
                    "completed", "on_hold", "rejected",
                ],
                "quality_inspections.result": [
                    "pending", "in_progress", "passed",
                    "failed", "conditional_accept",
                ],
                "equipment_maintenance.status": [
                    "scheduled", "in_progress", "completed",
                ],
                "equipment.status": ["operational", "degraded", "down"],
            },
        }
        meta_path = self.output_dir / "metadata.json"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        print(f"  [OK] metadata: {meta_path}")

        # ── Manifest (Phase 19.1 data pack contract) ───────────────────
        manifest = self._build_manifest(counts)
        manifest_path = self.output_dir / "manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        print(f"  [OK] manifest: {manifest_path}")

        total = sum(counts.values())
        print(f"\n{'=' * 60}")
        print(f"  {total:,} total rows across {len(counts)} tables")
        print(f"  Output: {self.output_dir}")
        print(f"{'=' * 60}")

        return counts


# ── CLI ───────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate synthetic manufacturing datasets",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                                    # default scale
  %(prog)s --preset tiny                      # smoke test
  %(prog)s --preset medium                    # pilot
  %(prog)s --preset enterprise                # stress test
  %(prog)s --num-products 200 --num-materials 1000 --num-work-orders 5000
        """,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "data" / "manufacturing",
        help="Output directory (default: data/manufacturing)",
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed for reproducibility (default: 42)",
    )
    parser.add_argument(
        "--num-suppliers", type=int, default=20,
        help="Number of suppliers",
    )
    parser.add_argument(
        "--num-materials", type=int, default=200,
        help="Number of raw materials / components",
    )
    parser.add_argument(
        "--num-products", type=int, default=50,
        help="Number of finished products",
    )
    parser.add_argument(
        "--num-work-centers", type=int, default=10,
        help="Number of work centers / production lines",
    )
    parser.add_argument(
        "--num-work-orders", type=int, default=500,
        help="Number of production work orders",
    )
    parser.add_argument(
        "--days-of-history", type=int, default=365,
        help="Days of historical data to generate",
    )
    parser.add_argument(
        "--preset",
        choices=["tiny", "small", "medium", "large", "enterprise"],
        default=None,
        help="Scale preset (overrides individual --num-* args)",
    )
    args = parser.parse_args()

    presets = {
        "tiny":       (3,   15,   5,   3,    10),
        "small":      (10,  50,   15,  5,    50),
        "medium":     (20,  200,  50,  10,   500),
        "large":      (50,  500,  200, 20,   2000),
        "enterprise": (100, 2000, 500, 50,   10000),
    }
    if args.preset:
        (
            args.num_suppliers,
            args.num_materials,
            args.num_products,
            args.num_work_centers,
            args.num_work_orders,
        ) = presets[args.preset]
        print(
            f"Preset '{args.preset}': {args.num_products} products, "
            f"{args.num_materials} materials, "
            f"{args.num_work_orders} work orders\n"
        )

    cfg = Config(
        seed=args.seed,
        num_suppliers=args.num_suppliers,
        num_materials=args.num_materials,
        num_products=args.num_products,
        num_work_centers=args.num_work_centers,
        num_work_orders=args.num_work_orders,
        days_of_history=args.days_of_history,
    )
    cfg._preset_name = args.preset or "custom"

    gen = ManufacturingGenerator(cfg, args.output_dir)
    gen.run()


if __name__ == "__main__":
    main()
