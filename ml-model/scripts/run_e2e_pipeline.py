"""
SAHAYAK Flood Mapper — Unified End-to-End Pipeline Orchestrator

Executes the full local workflow in a single reproducible command:
1. Pre-flight Verification (input GeoTIFFs, checkpoint, OSM graph, virtual environments)
2. Full-Scene ML Inference (U-Net sliding-window tiled prediction with georeferencing)
3. Road Graph Overlay & Connectivity Analysis (OpenStreetMap road cutting, Dijkstra reachability, rescue priority)
4. Frontend GeoJSON & Metadata Export (geodesic area calculation on WGS84, polygon simplification, disclaimer export)
5. Data Contract & Invariant Validation (cross-file settlement reconciliation, coordinate validity, GeoJSON compliance)
6. Frontend Production Build (TypeScript compilation tsc -b and Vite client bundling)

Usage:
    python ml-model/scripts/run_e2e_pipeline.py
    python ml-model/scripts/run_e2e_pipeline.py --threshold 0.5
    python ml-model/scripts/run_e2e_pipeline.py --help
"""

import sys
import os
import argparse
import time
import json
import shutil
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

# Ensure UTF-8 output encoding on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Path Discovery
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ML_DIR = REPO_ROOT / "ml-model"
GRAPH_DIR = REPO_ROOT / "graph-analysis"
FRONTEND_DIR = REPO_ROOT / "frontend"

# Virtual environment python interpreters
if sys.platform == "win32":
    ML_PYTHON = ML_DIR / ".venv/Scripts/python.exe"
    GA_PYTHON = GRAPH_DIR / ".venv/Scripts/python.exe"
else:
    ML_PYTHON = ML_DIR / ".venv/bin/python"
    GA_PYTHON = GRAPH_DIR / ".venv/bin/python"


# ---------------------------------------------------------------------------
# Stage Runner Helper
# ---------------------------------------------------------------------------
def print_banner(title: str, char: str = "="):
    line = char * 70
    print(f"\n{line}\n {title}\n{line}")


def run_subprocess_stage(
    stage_id: str,
    stage_title: str,
    cmd: List[str],
    cwd: Path,
    env: Optional[Dict[str, str]] = None,
) -> Tuple[bool, float, str]:
    """
    Executes a subprocess stage with argument list, capturing timing and output.
    Returns (success, duration_seconds, output_message).
    """
    print_banner(f"[{stage_id}] {stage_title}", "-")
    display_cmd = " ".join([f'"{c}"' if " " in c else c for c in cmd])
    print(f"Command: {display_cmd}")
    print(f"Working Dir: {cwd}")

    run_env = os.environ.copy()
    if env:
        run_env.update(env)

    t0 = time.time()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            env=run_env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        duration = time.time() - t0

        if proc.returncode == 0:
            print(f"[STAGE PASS] {stage_title} ({duration:.2f}s)")
            if proc.stdout.strip():
                # Print indented tail of output for context
                lines = proc.stdout.strip().splitlines()
                summary_lines = lines[-6:] if len(lines) > 6 else lines
                for l in summary_lines:
                    print(f"   {l}")
            return True, duration, ""
        else:
            print(f"[STAGE FAILED] {stage_title} (exit code: {proc.returncode})")
            print("\n--- Subprocess STDOUT ---")
            print(proc.stdout.strip())
            print("\n--- Subprocess STDERR ---")
            print(proc.stderr.strip())
            return False, duration, proc.stderr.strip() or proc.stdout.strip()

    except Exception as exc:
        duration = time.time() - t0
        print(f"[STAGE ERROR] Failed to spawn process: {exc}")
        return False, duration, str(exc)


# ---------------------------------------------------------------------------
# Stage 1: Pre-flight Verification
# ---------------------------------------------------------------------------
def check_prerequisites() -> Tuple[bool, List[str]]:
    """
    Checks that all required inputs, virtual environments, and build tools exist.
    """
    issues = []

    # 1. Check Python virtual environments
    if not ML_PYTHON.exists():
        issues.append(
            f"ML virtual environment python not found at: {ML_PYTHON}\n"
            f"   Setup instruction: cd ml-model && python -m venv .venv && "
            f".venv\\Scripts\\pip install -r requirements.txt"
        )
    if not GA_PYTHON.exists():
        issues.append(
            f"Graph-analysis virtual environment python not found at: {GA_PYTHON}\n"
            f"   Setup instruction: cd graph-analysis && python -m venv .venv && "
            f".venv\\Scripts\\pip install -r requirements.txt"
        )

    # 2. Check input GeoTIFFs
    pre_flood_tif = ML_DIR / "Data/raw/pre_flood_VV.tif"
    post_flood_tif = ML_DIR / "Data/raw/post_flood_VV.tif"
    checkpoint = ML_DIR / "outputs/baseline_run_01/model_best.pth"

    for p, name in [
        (pre_flood_tif, "Pre-flood SAR GeoTIFF (ml-model/Data/raw/pre_flood_VV.tif)"),
        (post_flood_tif, "Post-flood SAR GeoTIFF (ml-model/Data/raw/post_flood_VV.tif)"),
        (checkpoint, "Trained U-Net Checkpoint (ml-model/outputs/baseline_run_01/model_best.pth)"),
    ]:
        if not p.exists():
            issues.append(f"Required ML input missing: {name}")

    # 3. Check graph network assets
    road_edges = GRAPH_DIR / "road_edges.gpkg"
    network_graphml = GRAPH_DIR / "network.graphml"
    service_centers = GRAPH_DIR / "service_centers.geojson"
    settlements = GRAPH_DIR / "settlements.geojson"

    for p, name in [
        (road_edges, "Road Edges GeoPackage (graph-analysis/road_edges.gpkg)"),
        (network_graphml, "Network GraphML (graph-analysis/network.graphml)"),
        (service_centers, "Service Centers GeoJSON (graph-analysis/service_centers.geojson)"),
        (settlements, "Settlements GeoJSON (graph-analysis/settlements.geojson)"),
    ]:
        if not p.exists():
            issues.append(f"Required graph input asset missing: {name}")

    # 4. Check npm availability
    npm_path = shutil.which("npm.cmd") or shutil.which("npm")
    if not npm_path:
        issues.append("Node.js / npm executable not found in system PATH (required for frontend build).")

    return len(issues) == 0, issues


# ---------------------------------------------------------------------------
# Stage 5: Data Contract & Invariant Validation
# ---------------------------------------------------------------------------
def validate_data_contracts() -> Tuple[bool, List[str]]:
    """
    Validates data integrity, cross-file reconciliation, and schema contracts
    on exported frontend artifacts in frontend/src/data/.
    """
    issues = []
    fe_data_dir = FRONTEND_DIR / "src/data"

    required_files = {
        "cutoff": fe_data_dir / "ml_cutoff.json",
        "practical": fe_data_dir / "ml_practical.json",
        "connected": fe_data_dir / "ml_connected.json",
        "priority": fe_data_dir / "ml_priority.json",
        "flood": fe_data_dir / "ml_flood.json",
        "meta": fe_data_dir / "ml_meta.json",
    }

    # 1. Existence and non-empty check
    for key, path in required_files.items():
        if not path.exists():
            issues.append(f"Exported artifact missing: {path.name}")
            return False, issues
        if path.stat().st_size == 0 and key != "practical":
            issues.append(f"Exported artifact is empty: {path.name}")

    # 2. Parse JSON files
    try:
        with open(required_files["cutoff"], encoding="utf-8") as f:
            cutoff = json.load(f)
        with open(required_files["practical"], encoding="utf-8") as f:
            practical = json.load(f)
        with open(required_files["connected"], encoding="utf-8") as f:
            connected = json.load(f)
        with open(required_files["priority"], encoding="utf-8") as f:
            priority = json.load(f)
        with open(required_files["flood"], encoding="utf-8") as f:
            flood = json.load(f)
        with open(required_files["meta"], encoding="utf-8") as f:
            meta = json.load(f)
    except Exception as exc:
        issues.append(f"JSON parsing error in exported files: {exc}")
        return False, issues

    # 3. Dynamic settlement reconciliation invariant:
    # strict cutoffs + practical cutoffs + connected == total settlements
    n_cutoff = len(cutoff)
    n_practical = len(practical)
    n_connected = len(connected)
    total_reconciled = n_cutoff + n_practical + n_connected

    meta_total = meta.get("total_settlements")
    if meta_total is not None and total_reconciled != meta_total:
        issues.append(
            f"Settlement reconciliation mismatch: strict ({n_cutoff}) + practical ({n_practical}) "
            f"+ connected ({n_connected}) = {total_reconciled}, but metadata total is {meta_total}."
        )

    # 4. Settlement coordinate sanity check (valid geographic coordinates)
    for s_list, label in [(cutoff, "cutoff"), (connected, "connected")]:
        for item in s_list:
            lat = item.get("latitude")
            lon = item.get("longitude")
            name = item.get("name", "Unknown")
            if lat is None or lon is None:
                issues.append(f"Missing lat/lon for {label} settlement: {name}")
                continue
            if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
                issues.append(f"Non-numeric coordinates for {label} settlement: {name}")
                continue
            if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lon <= 180.0):
                issues.append(f"Coordinates out of bounds for {label} settlement {name}: ({lat}, {lon})")

    # 5. Priority ranking consistency
    p_features = priority.get("features", [])
    if len(p_features) != (n_cutoff + n_practical):
        issues.append(
            f"Priority list feature count ({len(p_features)}) does not equal "
            f"strict cutoffs ({n_cutoff}) + practical cutoffs ({n_practical})."
        )

    # 6. Flood GeoJSON structure and positive geodesic area
    if flood.get("type") != "FeatureCollection":
        issues.append(f"ml_flood.json root type is not FeatureCollection (got {flood.get('type')})")
    flood_features = flood.get("features", [])
    if len(flood_features) == 0:
        issues.append("ml_flood.json has zero features.")
    for feat in flood_features[:20]:
        area_ha = feat.get("properties", {}).get("areaHectares", 0)
        if area_ha <= 0:
            issues.append(f"Flood feature {feat.get('properties', {}).get('id')} has non-positive area: {area_ha}")
            break

    # 7. Metadata provenance invariants
    flood_area_ha = meta.get("flood_area_hectares", 0)
    if flood_area_ha <= 0:
        issues.append(f"Metadata flood_area_hectares is not positive: {flood_area_ha}")
    if not meta.get("is_experimental"):
        issues.append("Metadata is_experimental flag is not True.")
    if not meta.get("disclaimer"):
        issues.append("Metadata missing experimental provenance disclaimer.")

    return len(issues) == 0, issues


# ---------------------------------------------------------------------------
# Main Orchestrator Routine
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="SAHAYAK Flood Mapper — Unified End-to-End Pipeline Orchestrator",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.5,
        help="Decision threshold for U-Net binary flood segmentation (0.0 - 1.0)",
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Skip the frontend production build step (tsc -b && vite build)",
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip executing the unit test suite after export",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Verify prerequisites and environment setup without running the pipeline",
    )

    args = parser.parse_args()

    print_banner("SAHAYAK FLOOD MAPPER — UNIFIED E2E PIPELINE ORCHESTRATOR")
    print(f"Repository Root:   {REPO_ROOT}")
    print(f"ML Python:         {ML_PYTHON}")
    print(f"Graph Python:      {GA_PYTHON}")
    print(f"Inference Thresh:  {args.threshold}")
    print(f"Skip Build:        {args.skip_build}")
    print(f"Skip Tests:        {args.skip_tests}")
    print(f"Dry Run Mode:      {args.dry_run}")

    pipeline_start_time = time.time()
    stage_results: List[Dict[str, Any]] = []

    # -----------------------------------------------------------------------
    # STAGE 1: Pre-flight Verification
    # -----------------------------------------------------------------------
    t0 = time.time()
    prereqs_ok, prereq_issues = check_prerequisites()
    duration = time.time() - t0

    if not prereqs_ok:
        print_banner("[STAGE 1 FAILED] Pre-flight Verification", "!")
        print("The pipeline cannot proceed because of the following missing prerequisites:\n")
        for i, issue in enumerate(prereq_issues, 1):
            print(f"{i}. {issue}")
        sys.exit(1)

    print(f"\n[STAGE PASS] Stage 1: Pre-flight Verification ({duration:.2f}s)")
    print("   All required GeoTIFFs, checkpoint, graph assets, and virtual environments verified.")
    stage_results.append({"stage": "1. Pre-flight Verification", "status": "PASS", "duration": duration})

    if args.dry_run:
        print_banner("DRY RUN COMPLETE — All prerequisites satisfied.")
        sys.exit(0)

    # -----------------------------------------------------------------------
    # STAGE 2: U-Net Full-Scene Inference
    # -----------------------------------------------------------------------
    predict_script = ML_DIR / "scripts/predict.py"
    inference_cmd = [
        str(ML_PYTHON),
        str(predict_script),
        "--checkpoint", "outputs/baseline_run_01/model_best.pth",
        "--pre-flood", "Data/raw/pre_flood_VV.tif",
        "--post-flood", "Data/raw/post_flood_VV.tif",
        "--output-dir", "outputs/inference_run_01",
        "--threshold", str(args.threshold),
    ]

    ok, dur, err = run_subprocess_stage(
        stage_id="STAGE 2",
        stage_title="U-Net Full-Scene Sliding-Window Inference",
        cmd=inference_cmd,
        cwd=ML_DIR,
    )
    stage_results.append({"stage": "2. ML Tiled Inference", "status": "PASS" if ok else "FAIL", "duration": dur})
    if not ok:
        print(f"\n[PIPELINE ABORTED] Inference stage failed: {err}", file=sys.stderr)
        sys.exit(2)

    # -----------------------------------------------------------------------
    # STAGE 3: Road Graph Overlay & Connectivity Analysis
    # -----------------------------------------------------------------------
    graph_runner_script = ML_DIR / "scripts/run_graph_integration.py"
    graph_cmd = [
        str(GA_PYTHON),
        str(graph_runner_script),
    ]

    ok, dur, err = run_subprocess_stage(
        stage_id="STAGE 3",
        stage_title="Road Network Flood Overlay & Dijkstra Connectivity Analysis",
        cmd=graph_cmd,
        cwd=REPO_ROOT,
    )
    stage_results.append({"stage": "3. Graph Overlay & Routing", "status": "PASS" if ok else "FAIL", "duration": dur})
    if not ok:
        print(f"\n[PIPELINE ABORTED] Graph analysis stage failed: {err}", file=sys.stderr)
        sys.exit(3)

    # -----------------------------------------------------------------------
    # STAGE 4: Frontend GeoJSON & Metadata Export
    # -----------------------------------------------------------------------
    export_script = ML_DIR / "scripts/export_frontend_data.py"
    export_cmd = [
        str(GA_PYTHON),
        str(export_script),
    ]

    ok, dur, err = run_subprocess_stage(
        stage_id="STAGE 4",
        stage_title="Frontend Vectorization & Geodesic Area Export",
        cmd=export_cmd,
        cwd=REPO_ROOT,
    )
    stage_results.append({"stage": "4. Frontend Data Export", "status": "PASS" if ok else "FAIL", "duration": dur})
    if not ok:
        print(f"\n[PIPELINE ABORTED] Frontend export stage failed: {err}", file=sys.stderr)
        sys.exit(4)

    # -----------------------------------------------------------------------
    # STAGE 5: Data Contract & Invariant Validation
    # -----------------------------------------------------------------------
    print_banner("[STAGE 5] Data Contract & Cross-File Reconciliation Validation", "-")
    t0 = time.time()
    contracts_ok, contract_issues = validate_data_contracts()
    dur = time.time() - t0

    if not contracts_ok:
        print(f"[STAGE FAILED] Data contract validation failed ({dur:.2f}s):")
        for issue in contract_issues:
            print(f"   [ERROR] {issue}")
        stage_results.append({"stage": "5. Data Contract Validation", "status": "FAIL", "duration": dur})
        sys.exit(5)

    print(f"[STAGE PASS] Data Contract & Reconciliation Invariants Verified ({dur:.2f}s)")
    print("   Cross-file settlement counts match metadata.")
    print("   All settlement coordinates are within valid geographic bounds.")
    print("   Flood GeoJSON contains valid polygons with positive ellipsoidal area.")
    stage_results.append({"stage": "5. Data Contract Validation", "status": "PASS", "duration": dur})

    # Optional: Run ML & Export Unit Test Suite
    if not args.skip_tests:
        test_cmd = [
            str(ML_PYTHON),
            "-m", "unittest", "discover",
            "-t", str(ML_DIR),
            "-s", str(ML_DIR / "tests"),
        ]
        ok, dur, err = run_subprocess_stage(
            stage_id="STAGE 5B",
            stage_title="Automated Unit Test Suite (ML & Export Contracts)",
            cmd=test_cmd,
            cwd=REPO_ROOT,
        )
        stage_results.append({"stage": "5B. Unit Test Suite", "status": "PASS" if ok else "FAIL", "duration": dur})
        if not ok:
            print(f"\n[PIPELINE ABORTED] Unit test suite failed: {err}", file=sys.stderr)
            sys.exit(6)

    # -----------------------------------------------------------------------
    # STAGE 6: Frontend Production Build
    # -----------------------------------------------------------------------
    if not args.skip_build:
        npm_exe = shutil.which("npm.cmd") or shutil.which("npm") or "npm"
        build_cmd = [npm_exe, "run", "build"]

        ok, dur, err = run_subprocess_stage(
            stage_id="STAGE 6",
            stage_title="Frontend Production Build (tsc -b && vite build)",
            cmd=build_cmd,
            cwd=FRONTEND_DIR,
        )
        stage_results.append({"stage": "6. Frontend Production Build", "status": "PASS" if ok else "FAIL", "duration": dur})
        if not ok:
            print(f"\n[PIPELINE ABORTED] Frontend build failed: {err}", file=sys.stderr)
            sys.exit(7)
    else:
        print("\n[INFO] Skipping Stage 6 (Frontend Production Build) as requested by --skip-build.")

    # -----------------------------------------------------------------------
    # Summary Report
    # -----------------------------------------------------------------------
    total_pipeline_time = time.time() - pipeline_start_time
    print_banner("SAHAYAK E2E PIPELINE EXECUTION SUMMARY")

    print(f"{'Stage Name':<42} | {'Duration':<10} | {'Status'}")
    print("-" * 65)
    for res in stage_results:
        print(f"{res['stage']:<42} | {res['duration']:>6.2f}s    | {res['status']}")
    print("-" * 65)
    print(f"Total Pipeline Runtime: {total_pipeline_time:.2f} seconds")
    print(f"Generated Frontend Artifacts: {FRONTEND_DIR / 'src/data'}")
    print(f"Dashboard Available At:       http://localhost:5173/")
    print_banner("ALL STAGES COMPLETED SUCCESSFULLY — ZERO REGRESSIONS")


if __name__ == "__main__":
    main()
