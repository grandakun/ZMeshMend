"""ZMeshMend CGAL Pipeline Helper (Standalone)

Called by the ZScript plugin to run the CGAL hole-filling pipeline externally.
No ZBrush dependency - pure Python + OS.

Usage:
    python ZMeshMend_pipeline.py <input_obj> <output_obj> [--cgal-exe PATH] [--no-merge]
"""

import os
import sys
import subprocess
import math

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def log(msg):
    print(f"[ZMeshMend Pipeline] {msg}")


def _read_obj_full(filepath):
    vertices = []
    faces = []
    groups = []
    current_group = "default"
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            if s.startswith("v "):
                parts = s.split()
                vertices.append((float(parts[1]), float(parts[2]), float(parts[3])))
            elif s.startswith("f "):
                idx = []
                for tok in s[2:].split():
                    raw = tok.split("/")[0]
                    n = int(raw)
                    if n < 0:
                        n = len(vertices) + n + 1
                    idx.append(n)
                faces.append(idx)
                groups.append(current_group)
            elif s.startswith("g "):
                current_group = s[2:].strip() or "default"
    return vertices, faces, groups


def _write_obj_full(filepath, vertices, faces, groups):
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("# ZMeshMend CGAL merged mesh\n")
        f.write(f"# vertices: {len(vertices)} faces: {len(faces)}\n")
        for v in vertices:
            f.write(f"v {v[0]:.9f} {v[1]:.9f} {v[2]:.9f}\n")
        cur = None
        for i, face in enumerate(faces):
            g = groups[i] if i < len(groups) else "default"
            if g != cur:
                cur = g
                f.write(f"g {g}\n")
            f.write("f " + " ".join(str(x) for x in face) + "\n")


def merge_obj_with_patch(orig_obj, patch_obj, out_obj, weld_eps=None):
    try:
        ov, of, og = _read_obj_full(orig_obj)
        pv, pf, _ = _read_obj_full(patch_obj)
    except Exception as e:
        log(f"OBJ merge read failed: {e}")
        return False, 0

    if not pf:
        log("Patch is empty, nothing to merge")
        return False, 0

    if weld_eps is None or weld_eps <= 0:
        if ov:
            xs = [v[0] for v in ov]
            ys = [v[1] for v in ov]
            zs = [v[2] for v in ov]
            diag = (
                (max(xs) - min(xs)) ** 2
                + (max(ys) - min(ys)) ** 2
                + (max(zs) - min(zs)) ** 2
            ) ** 0.5
            weld_eps = max(diag * 1e-5, 1e-5)
        else:
            weld_eps = 1e-5
    log(f"Weld tolerance: {weld_eps:.6g}")

    grid = {}
    cell = max(weld_eps * 2.0, 1e-12)

    def _key(p):
        return (int(p[0] // cell), int(p[1] // cell), int(p[2] // cell))

    for i, v in enumerate(ov):
        grid.setdefault(_key(v), []).append(i + 1)

    eps2 = weld_eps * weld_eps
    patch_remap = {}
    next_idx = len(ov)
    new_verts = list(ov)
    welded_count = 0

    for pi, pv_ in enumerate(pv):
        kx, ky, kz = _key(pv_)
        best = -1
        best_d2 = eps2
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    bucket = grid.get((kx + dx, ky + dy, kz + dz))
                    if not bucket:
                        continue
                    for cand in bucket:
                        ov_ = new_verts[cand - 1]
                        d2 = (
                            (ov_[0] - pv_[0]) ** 2
                            + (ov_[1] - pv_[1]) ** 2
                            + (ov_[2] - pv_[2]) ** 2
                        )
                        if d2 < best_d2:
                            best_d2 = d2
                            best = cand
        if best > 0:
            patch_remap[pi + 1] = best
            welded_count += 1
        else:
            next_idx += 1
            new_verts.append(pv_)
            patch_remap[pi + 1] = next_idx
            grid.setdefault((kx, ky, kz), []).append(next_idx)

    new_faces = list(of)
    new_groups = list(og)

    fill_count = 0
    for face in pf:
        mapped = [patch_remap[v] for v in face]
        new_faces.append(mapped)
        new_groups.append("ZMeshMend_Fill")
        fill_count += 1

    try:
        _write_obj_full(out_obj, new_verts, new_faces, new_groups)
    except Exception as e:
        log(f"OBJ merge write failed: {e}")
        return False, 0

    log(
        f"Merged OBJ: orig={len(ov)}v/{len(of)}f, "
        f"patch={len(pv)}v/{len(pf)}f, "
        f"welded={welded_count}/{len(pv)}, "
        f"final={len(new_verts)}v/{len(new_faces)}f, "
        f"fill_faces={fill_count}"
    )
    return True, fill_count


def call_cgal_fill(input_obj, output_patch, cgal_exe_path):
    log(f"CGAL exe: {cgal_exe_path}")
    log(f"Input:    {input_obj}")
    log(f"Output:   {output_patch}")

    if not os.path.exists(cgal_exe_path):
        log(f"ERROR: CGAL exe not found at {cgal_exe_path}")
        return False

    args = [cgal_exe_path, input_obj, output_patch]

    try:
        p = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=300,
            cwd=_SCRIPT_DIR,
        )
        if p.stdout:
            for line in p.stdout.strip().split("\n"):
                log(f"  [CGAL] {line.strip()}")
        if p.stderr:
            for line in p.stderr.strip().split("\n"):
                if line.strip():
                    log(f"  [CGAL ERR] {line.strip()}")

        if p.returncode != 0:
            log(f"CGAL exe returned error code {p.returncode}")
            return False

        if not os.path.exists(output_patch):
            log("CGAL output file not created")
            return False

        return True
    except FileNotFoundError:
        log(f"CGAL exe not found: {cgal_exe_path}")
        return False
    except subprocess.TimeoutExpired:
        log("CGAL exe timed out after 300s")
        return False
    except Exception as e:
        log(f"CGAL error: {e}")
        return False


def main():
    import argparse

    parser = argparse.ArgumentParser(description="ZMeshMend CGAL Pipeline")
    parser.add_argument("input_obj", help="Input OBJ file path")
    parser.add_argument("output_obj", help="Output OBJ file path (merged result)")
    parser.add_argument(
        "--cgal-exe",
        default=None,
        help="Path to zmeshmend_core.exe (default: ../zmeshmend_core.exe)",
    )
    parser.add_argument(
        "--no-merge",
        action="store_true",
        help="Skip merge step (CGAL fills directly into input, output is patch only)",
    )
    args = parser.parse_args()

    input_obj = os.path.abspath(args.input_obj)
    output_obj = os.path.abspath(args.output_obj)

    if not os.path.exists(input_obj):
        log(f"ERROR: Input OBJ not found: {input_obj}")
        sys.exit(1)

    cgal_exe = args.cgal_exe
    if cgal_exe is None:
        cgal_exe = os.path.join(_SCRIPT_DIR, "zmeshmend_core.exe")

    log("=" * 60)
    log("ZMeshMend CGAL Pipeline")
    log("=" * 60)

    import tempfile
    patch_obj = os.path.join(tempfile.gettempdir(), "zmeshmend_zscript_patch.obj")

    log("Step 1/2: Calling CGAL to fill holes...")
    success = call_cgal_fill(input_obj, patch_obj, cgal_exe)

    if not success:
        log("CGAL failed. Check that zmeshmend_core.exe is built and accessible.")
        sys.exit(1)

    if args.no_merge:
        log("Step 2/2: Skipping merge (--no-merge), copying patch to output...")
        import shutil
        shutil.copy(patch_obj, output_obj)
        log(f"Output (patch only): {output_obj}")
    else:
        log("Step 2/2: Merging fill patch with original mesh...")
        ok, fill_count = merge_obj_with_patch(input_obj, patch_obj, output_obj)
        if not ok or fill_count == 0:
            log("Merge failed or no fill faces. Copying original to output as fallback.")
            import shutil
            shutil.copy(input_obj, output_obj)
            sys.exit(1)

    try:
        os.remove(patch_obj)
    except Exception:
        pass

    log("=" * 60)
    log(f"Pipeline complete! Output: {output_obj}")
    log("=" * 60)


if __name__ == "__main__":
    main()
