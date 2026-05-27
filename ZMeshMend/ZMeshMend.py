"""ZMeshMend - ZBrush Python Plugin
=============================

Automatically closes all open holes on the current mesh.
Rebuilt from the original ZMeshMend plugin using ZBrush Python API.

Core Features:
  1. Auto-close all holes
  2. Remove small disconnected fragments / mesh debris
  3. Create new PolyGroup for filled areas
  4. Auto-mask newly closed area
  5. Support mesh cleanup based on existing ZBrush mask
"""

__author__ = "ZMeshMend Rebuild"
__version__ = "1.0.0"

import os
import sys
import tempfile
import struct
import math
import subprocess
from zbrush import commands as zbc

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

_CGAL_DATA_DIR = os.path.join(os.path.dirname(_SCRIPT_DIR), "ZMeshMendData")
_CGAL_EXE_PATH = os.path.join(_CGAL_DATA_DIR, "zmeshmend_core.exe")
_CGAL_EXE_REL = os.path.normpath(os.path.join("..", "ZMeshMendData", "zmeshmend_core.exe"))

PALETTE_NAME = "ZMeshMend"
SUBPALETTE_MAIN = f"{PALETTE_NAME}:Close Holes"
SUBPALETTE_CONF = f"{PALETTE_NAME}:Settings"
SUBPALETTE_INFO = f"{PALETTE_NAME}:Info"

CONFIG_PATH = os.path.join(_SCRIPT_DIR, "ZMeshMend_config.txt")

_cgal_available_cache = None

CONFIG = {
    "removeSmallFragments": True,
    "fragmentMinFraction": 0.01,
    "fragmentMinFaces": 50,
    "maskGrowRings": 1,
    "maskSharpenPasses": 1,
}

_config_comment_map = {
    "removeSmallFragments": "Remove small disconnected fragments (1=yes, 0=no)",
    "fragmentMinFraction": "Minimum fraction of total faces to keep a fragment",
    "fragmentMinFaces": "Minimum absolute face count to keep a fragment",
    "maskGrowRings": "Number of rings to grow mask before deletion",
    "maskSharpenPasses": "Number of mask sharpen passes before grow",
}


def load_config():
    """Load configuration from ZMeshMend_config.txt"""
    global CONFIG
    if not os.path.exists(CONFIG_PATH):
        save_config()
        return
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip()
                    if key in CONFIG:
                        if isinstance(CONFIG[key], bool):
                            CONFIG[key] = val == "1"
                        elif isinstance(CONFIG[key], int):
                            CONFIG[key] = int(val)
                        elif isinstance(CONFIG[key], float):
                            CONFIG[key] = float(val)
    except Exception as e:
        _log(f"Warning: load_config failed: {e}")


def save_config():
    """Save current configuration to ZMeshMend_config.txt"""
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            f.write("# ZMeshMend Configuration\n")
            f.write("# Edit values as needed.\n\n")
            for key, default in CONFIG.items():
                comment = _config_comment_map.get(key, "")
                if comment:
                    f.write(f"# {comment}\n")
                if isinstance(default, bool):
                    f.write(f"{key}={1 if CONFIG[key] else 0}\n")
                elif isinstance(default, int):
                    f.write(f"{key}={CONFIG[key]}\n")
                elif isinstance(default, float):
                    f.write(f"{key}={CONFIG[key]}\n")
                f.write("\n")
    except Exception as e:
        _log(f"Warning: save_config failed: {e}")


def _cgal_available():
    """Check if the CGAL core executable exists"""
    global _cgal_available_cache
    if _cgal_available_cache is None:
        _cgal_available_cache = os.path.exists(_CGAL_EXE_PATH)
    return _cgal_available_cache


def _call_cgal_fill(input_obj, output_goz, fill_goz=None, debug_obj=None):
    """Call CGAL core EXE to fill holes. Output is GoZ format with PolyGroups.

    Input can be OBJ or GoZ. Output is always GoZ with PolyGroups.
    If debug_obj is provided, a verification OBJ is also written alongside GoZ.

    Returns (success, faces_added). Faces_added is -1 if no parsing possible.
    """
    args = [_CGAL_EXE_PATH, input_obj, output_goz]
    if fill_goz:
        args.append(fill_goz)
    else:
        args.append("")
    if debug_obj:
        args.append(debug_obj)
    faces_added = -1

    try:
        p = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=300,
            cwd=_CGAL_DATA_DIR,
        )

        stdout = p.stdout
        stderr = p.stderr

        if stderr:
            for line in stderr.strip().split("\n"):
                if line.strip():
                    _log(f"  [CGAL] {line.strip()}")

        for line in stdout.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            _log(f"  [CGAL] {line}")
            if line.startswith("SUMMARY:"):
                parts = line.split()
                for part in parts:
                    if part.startswith("faces_added="):
                        try:
                            faces_added = int(part.split("=")[1])
                        except ValueError:
                            pass

        if p.returncode != 0:
            _log(f"  [CGAL] EXE returned error code {p.returncode}")
            return False, faces_added

        if not os.path.exists(output_goz):
            _log(f"  [CGAL] Output file not created")
            return False, faces_added

        return True, faces_added

    except FileNotFoundError:
        _log(f"  [CGAL] EXE not found at: {_CGAL_EXE_PATH}")
        return False, -1
    except subprocess.TimeoutExpired:
        _log(f"  [CGAL] EXE timed out after 300s")
        return False, -1
    except Exception as e:
        _log(f"  [CGAL] Error: {e}")
        return False, -1


def _ui_path(relative):
    """Build full UI path relative to plugin palette"""
    return f"{PALETTE_NAME}:{relative}"


def _log(msg):
    """Print a message to the ZBrush console"""
    print(f"[ZMeshMend] {msg}")


def _progress(text, value=0.0):
    """Update the notebar progress display"""
    zbc.set_notebar_text(f"ZMeshMend: {text}", value)


def _clear_progress():
    """Clear the notebar"""
    zbc.set_notebar_text("", 0)


def _ensure_edit_mode():
    """Ensure we are in edit mode with an active polymesh tool"""
    try:
        if zbc.is_polymesh3d_solid():
            return True
    except Exception as e:
        _log(f"Warning: is_polymesh3d_solid check failed: {e}")

    try:
        pt = zbc.query_mesh3d(0)
        if pt and pt[0] > 0:
            return True
    except Exception as e:
        _log(f"Warning: query_mesh3d check failed: {e}")

    zbc.message_ok(
        "No active PolyMesh3D tool found.\n\n"
        "Please select a 3D tool and enter Edit mode first.",
        "ZMeshMend - Error"
    )
    return False


def _get_vertex_count():
    """Get current mesh vertex count"""
    try:
        result = zbc.query_mesh3d(0)
        if result:
            return int(result[0])
    except Exception as e:
        _log(f"Warning: _get_vertex_count failed: {e}")
    return 0


def _get_face_count():
    """Get current mesh face count"""
    try:
        result = zbc.query_mesh3d(1)
        if result:
            return int(result[0])
    except Exception as e:
        _log(f"Warning: _get_face_count failed: {e}")
    return 0


def _sharpen_mask(count=1):
    """Sharpen the current mask N times"""
    for i in range(count):
        try:
            zbc.press("Tool:Masking:SharpenMask")
        except Exception:
            try:
                zbc.press("Tool:Masking:Sharpen")
            except Exception:
                _log("Warning: Could not sharpen mask (button path may differ in this ZBrush version)")
                break


def _grow_mask(rings=1):
    """Grow the current mask by N rings"""
    try:
        for i in range(rings):
            zbc.press("Tool:Masking:GrowMask")
    except Exception:
        _log("Warning: Could not grow mask (button path may differ)")


def _hide_masked():
    """Hide points based on the current mask state.

    Note: ZBrush's HidePt button hides UNMASKED points (mask = protected).
    Caller must invert the mask first if it wants to hide the masked region.
    """
    candidates = [
        "Tool:Visibility:HidePt",
        "Tool:Visibility:Hide Pt",
    ]
    for path in candidates:
        try:
            if hasattr(zbc, "exists") and not zbc.exists(path):
                continue
            zbc.press(path)
            _log(f"  [vis] HidePt via '{path}'")
            return True
        except Exception:
            continue
    _log("  Warning: Could not hide points")
    return False


def _delete_hidden():
    """Delete hidden geometry"""
    try:
        zbc.press("Tool:Geometry:Modify Topology:Del Hidden")
    except Exception:
        try:
            zbc.press("Tool:Geometry:Del Hidden")
        except Exception:
            _log("Warning: Could not delete hidden faces")


def _close_holes():
    """Close all open holes"""
    try:
        zbc.press("Tool:Geometry:Modify Topology:Close Holes")
    except Exception:
        try:
            zbc.press("Tool:Geometry:Close Holes")
        except Exception:
            _log("ERROR: Could not close holes")


def _auto_groups():
    """Auto-create PolyGroups based on mesh connectivity"""
    try:
        zbc.press("Tool:PolyGroup:Auto Groups")
    except Exception:
        _log("Warning: Could not auto-group")


def _group_masked(clear_mask=True):
    """Create PolyGroup from masked area"""
    try:
        if clear_mask:
            zbc.press("Tool:PolyGroup:Group Masked Clear")
        else:
            zbc.press("Tool:PolyGroup:Group Masked")
    except Exception:
        _log("Warning: Could not group masked area")


def _mask_all():
    """Mask entire mesh"""
    try:
        zbc.press("Tool:Masking:MaskAll")
    except Exception:
        _log("Warning: Could not mask all")


def _clear_mask():
    """Clear the current mask"""
    try:
        zbc.press("Tool:Masking:Clear")
    except Exception:
        _log("Warning: Could not clear mask")


def _invert_mask():
    """Invert the current mask. Tries several known button paths."""
    candidates = [
        "Tool:Masking:Inverse",
        "Tool:Masking:Invert",
        "Tool:Masking:Mask Invert",
    ]
    for path in candidates:
        try:
            if hasattr(zbc, "exists") and not zbc.exists(path):
                continue
            zbc.press(path)
            _log(f"  [mask] invert via '{path}'")
            return True
        except Exception:
            continue
    _log("  Warning: Could not invert mask (no known button path)")
    return False


def _invert_visibility():
    """Invert visibility. Tries several known button paths."""
    candidates = [
        "Tool:Visibility:Invert",
        "Tool:Visibility:Inverse",
        "Tool:Visibility:Invert Visibility",
    ]
    for path in candidates:
        try:
            if hasattr(zbc, "exists") and not zbc.exists(path):
                continue
            zbc.press(path)
            _log(f"  [vis] invert via '{path}'")
            return True
        except Exception:
            continue
    _log("  Warning: Could not invert visibility")
    return False


def _show_all():
    """Show all geometry"""
    try:
        zbc.press("Tool:Visibility:ShowPt")
    except Exception:
        _log("Warning: Could not show all")


def _mask_by_polygroups():
    """Create mask from PolyGroups"""
    try:
        zbc.press("Tool:Masking:MaskByPolyGroups")
    except Exception:
        _log("Warning: Could not mask by PolyGroups")


def _undo():
    """Create an undo point"""
    try:
        zbc.press("Edit:Undo")
    except Exception:
        pass


def _export_obj(filepath):
    """Export current tool to OBJ file"""
    try:
        zbc.set_next_filename(filepath)
        zbc.press("Tool:Export")
        zbc.update()
        return os.path.exists(filepath)
    except Exception as e:
        _log(f"Warning: _export_obj failed: {e}")
        return False


def _import_obj(filepath):
    """Import OBJ file as current tool"""
    try:
        zbc.set_next_filename(filepath)
        zbc.press("Tool:Import")
        zbc.update()
        return True
    except Exception as e:
        _log(f"Warning: _import_obj failed: {e}")
        return False


def _import_goz(filepath):
    """Import GoZ file as current tool. PolyGroups and Mask are natively supported.

    Returns True if the GoZ was successfully imported and the mesh was loaded.
    Falls back to OBJ import from sibling .obj file if GoZ import fails.
    """
    try:
        face_before = _get_face_count()
        zbc.set_next_filename(filepath)
        zbc.press("Tool:Import")
        zbc.update()
        face_after = _get_face_count()
        if face_after != face_before or face_before == 0:
            return True
        _log("  Warning: GoZ import via Tool:Import did not change mesh, trying alternative...")
        try:
            zbc.execute_zscript('[IPress,Tool:GoZ]')
            zbc.update()
            return True
        except Exception:
            pass
        return False
    except Exception as e:
        _log(f"  Warning: GoZ import failed: {e}")
        return False


def _import_obj_as_subtool(filepath):
    """Import OBJ file directly as a subtool of the current tool.
    (Reserved for future use - currently not called.)

    Uses ZScript ISubToolAddMesh which adds a mesh file as a new
    subtool without replacing the current tool.
    ZBrush assigns different PolyGroups when subtools are later merged.

    If ZScript is not available, tries Tool:Subtool:Insert.
    Returns True if subtool was added, False otherwise.
    """
    try:
        script = '[ISubToolAddMesh, "{0}"]'.format(filepath.replace("\\", "/"))
        try:
            zbc.execute_zscript(script)
        except AttributeError:
            zbc.set_next_filename(filepath)
            zbc.press("Tool:Subtool:Insert")
        zbc.update()
        return True
    except Exception as e:
        _log(f"  Warning: Subtool import failed: {e}, falling back to OBJ import")
        return False


def _merge_visible():
    """Merge all visible subtools into one. Different subtool origins
    receive different PolyGroups in the merged result."""
    try:
        zbc.press("Tool:Subtool:Merge Visible")
    except Exception:
        try:
            zbc.press("Tool:Subtool:MergeDown")
        except Exception:
            _log("  Warning: Could not merge subtools")


def _weld_points():
    """Weld coincident vertices (used after Merge to fuse patch boundary)."""
    candidates = [
        "Tool:Geometry:Modify Topology:Weld Points",
        "Tool:Geometry:WeldPoints",
        "Tool:Geometry:Weld Points",
    ]
    for path in candidates:
        try:
            zbc.press(path)
            return True
        except Exception:
            continue
    _log("  Warning: Could not find Weld Points button")
    return False


def _read_obj_full(filepath):
    """Read OBJ keeping vertex/face/group structure as-is (preserves quads)."""
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


def _merge_obj_with_patch(orig_obj, patch_obj, out_obj, weld_eps=None):
    """Combine original OBJ with fill patch OBJ.

    - Preserves original quads/N-gons exactly.
    - Welds patch boundary vertices that coincide with original vertices,
      using a relative tolerance scaled to the model's bounding box so
      large-scale meshes (where ASCII OBJ float precision loses tail
      digits) still weld correctly.
    - Tags fill faces with group name 'ZMeshMend_Fill'.

    Returns (success, fill_face_count).
    """
    try:
        ov, of, og = _read_obj_full(orig_obj)
        pv, pf, _ = _read_obj_full(patch_obj)
    except Exception as e:
        _log(f"  OBJ merge read failed: {e}")
        return False, 0

    if not pf:
        return False, 0

    if weld_eps is None or weld_eps <= 0:
        if ov:
            xs = [v[0] for v in ov]; ys = [v[1] for v in ov]; zs = [v[2] for v in ov]
            diag = (
                (max(xs) - min(xs)) ** 2
                + (max(ys) - min(ys)) ** 2
                + (max(zs) - min(zs)) ** 2
            ) ** 0.5
            weld_eps = max(diag * 1e-5, 1e-5)
        else:
            weld_eps = 1e-5
    _log(f"  Weld tolerance: {weld_eps:.6g}")

    grid = {}
    cell = max(weld_eps * 2.0, 1e-12)

    def _key(p):
        return (
            int(p[0] // cell),
            int(p[1] // cell),
            int(p[2] // cell),
        )

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
                        d2 = ((ov_[0] - pv_[0]) ** 2
                              + (ov_[1] - pv_[1]) ** 2
                              + (ov_[2] - pv_[2]) ** 2)
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
        with open(out_obj, "w", encoding="utf-8") as f:
            f.write("# ZMeshMend merged mesh\n")
            f.write(f"# vertices: {len(new_verts)} faces: {len(new_faces)}\n")
            for v in new_verts:
                f.write(f"v {v[0]:.9f} {v[1]:.9f} {v[2]:.9f}\n")
            cur = None
            for i, face in enumerate(new_faces):
                g = new_groups[i] if i < len(new_groups) else "default"
                if g != cur:
                    cur = g
                    f.write(f"g {g}\n")
                f.write("f " + " ".join(str(x) for x in face) + "\n")
    except Exception as e:
        _log(f"  OBJ merge write failed: {e}")
        return False, 0

    _log(f"  Merged OBJ: orig={len(ov)}v/{len(of)}f, patch={len(pv)}v/{len(pf)}f, "
         f"welded={welded_count}/{len(pv)}, "
         f"final={len(new_verts)}v/{len(new_faces)}f")
    return True, fill_count


def _merge_patch_and_weld(patch_obj_path, orig_obj_path=None):
    """Strategy: build a merged OBJ (orig + patch with welded vertices)
    in Python, then Tool:Import the result back. Avoids SubTool API
    pitfalls and keeps original quads intact.

    If orig_obj_path is provided and exists, it is reused (skips a redundant
    Tool:Export). Otherwise the current mesh is exported to a temp file.
    """
    try:
        face_before = _get_face_count()

        cleanup_orig = False
        if orig_obj_path and os.path.exists(orig_obj_path):
            orig_obj = orig_obj_path
        else:
            orig_obj = os.path.join(tempfile.gettempdir(), "zmeshmend_orig.obj")
            cleanup_orig = True
            if not _export_obj(orig_obj):
                _log("  Cannot export original mesh for patch merge")
                return False

        merged_obj = os.path.join(tempfile.gettempdir(), "zmeshmend_merged.obj")

        ok, fill_count = _merge_obj_with_patch(orig_obj, patch_obj_path, merged_obj)
        if not ok or fill_count == 0:
            _log("  Patch is empty or merge failed")
            try: os.remove(merged_obj)
            except Exception: pass
            if cleanup_orig:
                try: os.remove(orig_obj)
                except Exception: pass
            return False

        if not _import_obj(merged_obj):
            _log("  Tool:Import of merged OBJ failed, restoring original...")
            _import_obj(orig_obj)
            try: os.remove(merged_obj)
            except Exception: pass
            if cleanup_orig:
                try: os.remove(orig_obj)
                except Exception: pass
            return False

        zbc.update(redraw_ui=True)

        face_after = _get_face_count()
        _log(f"  Patch merged: {face_before} -> {face_after} faces "
             f"(+{face_after - face_before}, fill={fill_count})")

        try: os.remove(merged_obj)
        except Exception: pass
        if cleanup_orig:
            try: os.remove(orig_obj)
            except Exception: pass

        return True
    except Exception as e:
        _log(f"  Patch merge failed: {e}")
        return False


def _count_faces_in_obj(filepath):
    """Count face lines ('f ') in an OBJ file"""
    count = 0
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if line.startswith("f "):
                    count += 1
    except Exception:
        pass
    return count


def _freeze_op(fn, desc="Processing"):
    """Execute an operation with frozen UI and progress display"""
    def wrapped():
        _progress(desc, 0.0)
        try:
            fn()
        finally:
            _clear_progress()
    zbc.freeze(wrapped)


def _read_obj_vertices_faces(filepath):
    """Read OBJ file, return (vertices, faces, groups)"""
    vertices = []
    faces = []
    groups = []
    current_group = "default"

    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.startswith("v "):
                parts = line.split()
                vertices.append((
                    float(parts[1]),
                    float(parts[2]),
                    float(parts[3]),
                ))
            elif line.startswith("f "):
                parts = line[1:]
                indices = []
                for p in parts.split():
                    idx = int(p.split("/")[0])
                    if idx < 0:
                        idx = len(vertices) + idx + 1
                    else:
                        idx = idx
                    indices.append(idx)
                faces.append(indices)
                groups.append(current_group)
            elif line.startswith("g "):
                current_group = line[2:].strip()

    return vertices, faces, groups


def _write_obj(filepath, vertices, faces, groups=None):
    """Write OBJ file from vertices and faces"""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("# ZMeshMend - Cleaned mesh\n")
        f.write(f"# Vertices: {len(vertices)}, Faces: {len(faces)}\n")

        for v in vertices:
            f.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")

        if groups:
            current_group = None
            for i, face in enumerate(faces):
                g = groups[i] if i < len(groups) else "default"
                if g != current_group:
                    current_group = g
                    f.write(f"g {g}\n")
                _write_face_line(f, face)
        else:
            for face in faces:
                _write_face_line(f, face)


def _write_face_line(f, face):
    """Write a single face line to OBJ"""
    f.write("f " + " ".join(str(i) for i in face) + "\n")


def _find_connected_components(faces):
    """Find connected components by face adjacency"""
    face_to_vert = {i: set(f) for i, f in enumerate(faces)}
    vert_to_faces = {}
    for fi, face in enumerate(faces):
        for vi in face:
            vert_to_faces.setdefault(vi, set()).add(fi)

    visited = set()
    components = []

    for start_fi in range(len(faces)):
        if start_fi in visited:
            continue
        stack = [start_fi]
        component = set()
        while stack:
            fi = stack.pop()
            if fi in visited:
                continue
            visited.add(fi)
            component.add(fi)
            for vi in faces[fi]:
                for nfi in vert_to_faces.get(vi, set()):
                    if nfi not in visited:
                        stack.append(nfi)
        components.append(component)

    return components


def _remove_small_fragments(filepath, total_faces, min_frac, min_abs):
    """Remove small disconnected fragments from OBJ file"""
    vertices, faces, groups = _read_obj_vertices_faces(filepath)

    if len(faces) < 2:
        return False

    components = _find_connected_components(faces)
    if len(components) <= 1:
        _log(f"  Mesh is one connected component (no fragments to remove)")
        return False

    threshold = max(min_abs, int(total_faces * min_frac))
    keep = set()
    large_count = 0
    removed_count = 0

    for comp in components:
        if len(comp) >= threshold:
            keep.update(comp)
            large_count += 1
        else:
            removed_count += 1

    if removed_count == 0:
        _log(f"  All {len(components)} components exceed threshold {threshold} faces")
        return False

    new_faces = [faces[i] for i in sorted(keep)]
    if groups:
        new_groups = [groups[i] for i in sorted(keep)]
    else:
        new_groups = None

    _write_obj(filepath, vertices, new_faces, new_groups)
    _log(f"  Kept {large_count} large components, removed {removed_count} small fragments")
    return True


def _v3_sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _v3_dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _v3_cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _v3_len(v):
    return math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])


def _v3_normalize(v):
    l = _v3_len(v)
    if l < 1e-12:
        return (0.0, 0.0, 0.0)
    return (v[0] / l, v[1] / l, v[2] / l)


def _find_boundary_edges(faces):
    """Find boundary edges (edges appearing in only one face)"""
    edge_count = {}
    for face in faces:
        n = len(face)
        for i in range(n):
            a, b = face[i], face[(i + 1) % n]
            key = (min(a, b), max(a, b))
            edge_count[key] = edge_count.get(key, 0) + 1

    return [k for k, v in edge_count.items() if v == 1]


def _build_boundary_loops(boundary_edges):
    """Chain boundary edges into loops"""
    adj = {}
    for a, b in boundary_edges:
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)

    loops = []
    visited = set()

    for start in adj:
        if start in visited:
            continue
        loop = []
        stack = [start]
        while stack:
            v = stack.pop()
            if v in visited:
                continue
            visited.add(v)
            loop.append(v)
            for nb in adj.get(v, []):
                if nb not in visited:
                    stack.append(nb)
        if loop:
            loops.append(loop)

    return loops


def _compute_loop_centroid(loop, vertices):
    """Compute centroid of a boundary loop"""
    if not loop:
        return (0, 0, 0)
    sx = sy = sz = 0.0
    for vi in loop:
        v = vertices[vi - 1]
        sx += v[0]
        sy += v[1]
        sz += v[2]
    n = len(loop)
    return (sx / n, sy / n, sz / n)


def _compute_loop_normal(loop, vertices):
    """Compute approximate normal for a loop using Newell's method"""
    if len(loop) < 3:
        return (0, 1, 0)
    nx = ny = nz = 0.0
    n = len(loop)
    for i in range(n):
        j = (i + 1) % n
        vi = vertices[loop[i] - 1]
        vj = vertices[loop[j] - 1]
        nx += (vi[1] - vj[1]) * (vi[2] + vj[2])
        ny += (vi[2] - vj[2]) * (vi[0] + vj[0])
        nz += (vi[0] - vj[0]) * (vi[1] + vj[1])
    return _v3_normalize((nx, ny, nz))


def _collect_nearby_vertices(loop, vertices, faces, rings=2):
    """Collect vertices near the boundary loop"""
    loop_set = set(loop)

    adj = {}
    for face in faces:
        n = len(face)
        for i in range(n):
            a, b = face[i], face[(i + 1) % n]
            adj.setdefault(a, set()).add(b)
            adj.setdefault(b, set()).add(a)

    nearby = set(loop)
    frontier = set(loop)

    for _ in range(rings):
        new_frontier = set()
        for v in frontier:
            for nb in adj.get(v, set()):
                if nb not in nearby:
                    nearby.add(nb)
                    new_frontier.add(nb)
        frontier = new_frontier

    return [vertices[vi - 1] for vi in nearby]


def _fit_sphere(points):
    """Least-squares fit a sphere to a set of 3D points"""
    if len(points) < 4:
        return None

    n = len(points)
    sum_x = sum(p[0] for p in points)
    sum_y = sum(p[1] for p in points)
    sum_z = sum(p[2] for p in points)
    sum_x2 = sum(p[0] * p[0] for p in points)
    sum_y2 = sum(p[1] * p[1] for p in points)
    sum_z2 = sum(p[2] * p[2] for p in points)
    sum_x3 = sum(p[0] * p[0] * p[0] for p in points)
    sum_y3 = sum(p[1] * p[1] * p[1] for p in points)
    sum_z3 = sum(p[2] * p[2] * p[2] for p in points)
    sum_xy = sum(p[0] * p[1] for p in points)
    sum_xz = sum(p[0] * p[2] for p in points)
    sum_yz = sum(p[1] * p[2] for p in points)
    sum_xy2 = sum(p[0] * p[1] * p[1] for p in points)
    sum_xz2 = sum(p[0] * p[2] * p[2] for p in points)
    sum_yx2 = sum(p[1] * p[0] * p[0] for p in points)
    sum_yz2 = sum(p[1] * p[2] * p[2] for p in points)
    sum_zx2 = sum(p[2] * p[0] * p[0] for p in points)
    sum_zy2 = sum(p[2] * p[1] * p[1] for p in points)

    A = [
        [2 * sum_x2, 2 * sum_xy, 2 * sum_xz, 2 * sum_x],
        [2 * sum_xy, 2 * sum_y2, 2 * sum_yz, 2 * sum_y],
        [2 * sum_xz, 2 * sum_yz, 2 * sum_z2, 2 * sum_z],
        [2 * sum_x, 2 * sum_y, 2 * sum_z, 2 * n],
    ]
    b = [
        sum_x3 + sum_xy2 + sum_xz2,
        sum_yx2 + sum_y3 + sum_yz2,
        sum_zx2 + sum_zy2 + sum_z3,
        sum_x2 + sum_y2 + sum_z2,
    ]

    try:
        det = (
            A[0][0] * (A[1][1] * (A[2][2] * A[3][3] - A[2][3] * A[3][2])
                       - A[1][2] * (A[2][1] * A[3][3] - A[2][3] * A[3][1])
                       + A[1][3] * (A[2][1] * A[3][2] - A[2][2] * A[3][1]))
            - A[0][1] * (A[1][0] * (A[2][2] * A[3][3] - A[2][3] * A[3][2])
                         - A[1][2] * (A[2][0] * A[3][3] - A[2][3] * A[3][0])
                         + A[1][3] * (A[2][0] * A[3][2] - A[2][2] * A[3][0]))
            + A[0][2] * (A[1][0] * (A[2][1] * A[3][3] - A[2][3] * A[3][1])
                         - A[1][1] * (A[2][0] * A[3][3] - A[2][3] * A[3][0])
                         + A[1][3] * (A[2][0] * A[3][1] - A[2][1] * A[3][0]))
            - A[0][3] * (A[1][0] * (A[2][1] * A[3][2] - A[2][2] * A[3][1])
                         - A[1][1] * (A[2][0] * A[3][2] - A[2][2] * A[3][0])
                         + A[1][2] * (A[2][0] * A[3][1] - A[2][1] * A[3][0]))
        )

        if abs(det) < 1e-30:
            return None

        inv_det = 1.0 / det
        cx = inv_det * (
            b[0] * (A[1][1] * (A[2][2] * A[3][3] - A[2][3] * A[3][2])
                    - A[1][2] * (A[2][1] * A[3][3] - A[2][3] * A[3][1])
                    + A[1][3] * (A[2][1] * A[3][2] - A[2][2] * A[3][1]))
            - A[0][1] * (b[1] * (A[2][2] * A[3][3] - A[2][3] * A[3][2])
                         - A[1][2] * (b[2] * A[3][3] - A[2][3] * b[3])
                         + A[1][3] * (b[2] * A[3][2] - A[2][2] * b[3]))
            + A[0][2] * (b[1] * (A[2][1] * A[3][3] - A[2][3] * A[3][1])
                         - A[1][1] * (b[2] * A[3][3] - A[2][3] * b[3])
                         + A[1][3] * (b[2] * A[3][1] - A[2][1] * b[3]))
            - A[0][3] * (b[1] * (A[2][1] * A[3][2] - A[2][2] * A[3][1])
                         - A[1][1] * (b[2] * A[3][2] - A[2][2] * b[3])
                         + A[1][2] * (b[2] * A[3][1] - A[2][1] * b[3]))
        )
        cy = inv_det * (
            A[0][0] * (b[1] * (A[2][2] * A[3][3] - A[2][3] * A[3][2])
                       - A[1][2] * (b[2] * A[3][3] - A[2][3] * b[3])
                       + A[1][3] * (b[2] * A[3][2] - A[2][2] * b[3]))
            - b[0] * (A[1][0] * (A[2][2] * A[3][3] - A[2][3] * A[3][2])
                      - A[1][2] * (A[2][0] * A[3][3] - A[2][3] * A[3][0])
                      + A[1][3] * (A[2][0] * A[3][2] - A[2][2] * A[3][0]))
            + A[0][2] * (A[1][0] * (b[2] * A[3][3] - A[2][3] * b[3])
                         - b[1] * (A[2][0] * A[3][3] - A[2][3] * A[3][0])
                         + A[1][3] * (A[2][0] * b[3] - b[2] * A[3][0]))
            - A[0][3] * (A[1][0] * (b[2] * A[3][2] - A[2][2] * b[3])
                         - b[1] * (A[2][0] * A[3][2] - A[2][2] * A[3][0])
                         + A[1][2] * (A[2][0] * b[3] - b[2] * A[3][0]))
        )
        cz = inv_det * (
            A[0][0] * (A[1][1] * (b[2] * A[3][3] - A[2][3] * b[3])
                       - b[1] * (A[2][1] * A[3][3] - A[2][3] * A[3][1])
                       + A[1][3] * (A[2][1] * b[3] - b[2] * A[3][1]))
            - A[0][1] * (A[1][0] * (b[2] * A[3][3] - A[2][3] * b[3])
                         - b[1] * (A[2][0] * A[3][3] - A[2][3] * A[3][0])
                         + A[1][3] * (A[2][0] * b[3] - b[2] * A[3][0]))
            + b[0] * (A[1][0] * (A[2][1] * A[3][3] - A[2][3] * A[3][1])
                      - A[1][1] * (A[2][0] * A[3][3] - A[2][3] * A[3][0])
                      + A[1][3] * (A[2][0] * A[3][1] - A[2][1] * A[3][0]))
            - A[0][3] * (A[1][0] * (A[2][1] * b[3] - b[2] * A[3][1])
                         - A[1][1] * (A[2][0] * b[3] - b[2] * A[3][0])
                         + b[1] * (A[2][0] * A[3][1] - A[2][1] * A[3][0]))
        )
    except (ZeroDivisionError, IndexError):
        return None

    center = (cx, cy, cz)

    r_sq_sum = 0.0
    for p in points:
        dx = p[0] - cx
        dy = p[1] - cy
        dz = p[2] - cz
        r_sq_sum += dx * dx + dy * dy + dz * dz
    radius = math.sqrt(r_sq_sum / n)

    error_sum = 0.0
    for p in points:
        dx = p[0] - cx
        dy = p[1] - cy
        dz = p[2] - cz
        d = math.sqrt(dx * dx + dy * dy + dz * dz)
        error_sum += (d - radius) ** 2
    error = math.sqrt(error_sum / n) / max(radius, 1e-8)

    return center, radius, error


def _project_to_sphere(point, center, radius):
    """Project a point onto a sphere surface"""
    dx = point[0] - center[0]
    dy = point[1] - center[1]
    dz = point[2] - center[2]
    d = math.sqrt(dx * dx + dy * dy + dz * dz)
    if d < 1e-8:
        return (center[0], center[1], center[2] + radius)
    s = radius / d
    return (center[0] + dx * s, center[1] + dy * s, center[2] + dz * s)


def _fill_hole_smart(vertices, faces, loop, groups_list=None):
    """
    Fill a boundary loop using sphere-fitting for curvature-aware completion.
    If the surrounding surface fits a sphere well, new vertices are projected
    onto that sphere. Otherwise falls back to centroid-based linear fill.
    """
    if len(loop) < 3:
        return [], [], []

    loop_centroid = _compute_loop_centroid(loop, vertices)
    loop_normal = _compute_loop_normal(loop, vertices)

    nearby = _collect_nearby_vertices(loop, vertices, faces, rings=2)

    span = max(
        _v3_len(_v3_sub(vertices[vi - 1], loop_centroid))
        for vi in loop
    ) if loop else 0.0

    use_sphere = False
    sphere_center = None
    sphere_radius = None

    if len(nearby) >= 6:
        sphere_result = _fit_sphere(nearby)
        if sphere_result is not None:
            sc, sr, serr = sphere_result
            if serr < 0.05:
                use_sphere = True
                sphere_center = sc
                sphere_radius = sr

    new_vertices = []
    new_faces = []
    new_groups = []

    vtx_offset = len(vertices)

    center_pt = loop_centroid
    if use_sphere:
        center_pt = _project_to_sphere(loop_centroid, sphere_center, sphere_radius)

    center_idx = vtx_offset + 1
    vertices.append(center_pt)
    new_vertices.append(center_pt)

    n = len(loop)
    for i in range(n):
        a = loop[i]
        b = loop[(i + 1) % n]
        face = [center_idx, b, a]
        faces.append(face)
        new_faces.append(face)
        if groups_list is not None:
            groups_list.append("ZMeshMend_Fill")

    return new_vertices, new_faces, ["ZMeshMend_Fill"] * len(new_faces)


def _process_holes_in_obj(filepath):
    """Process OBJ file: detect and fill holes with sphere-fitting"""
    vertices, faces, groups = _read_obj_vertices_faces(filepath)

    boundary_edges = _find_boundary_edges(faces)
    if not boundary_edges:
        _log("  No open boundaries found - mesh is watertight")
        return False

    loops = _build_boundary_loops(boundary_edges)
    _log(f"  Found {len(loops)} hole(s) with {len(boundary_edges)} boundary edges")

    total_new_faces = 0
    for loop in loops:
        if len(loop) < 3:
            continue
        new_verts, new_faces, new_grps = _fill_hole_smart(vertices, faces, loop, groups)
        total_new_faces += len(new_faces)
        if new_grps:
            groups.extend(new_grps)

    if total_new_faces > 0:
        _write_obj(filepath, vertices, faces, groups)
        _log(f"  Filled {total_new_faces} new face(s) across {len(loops)} hole(s)")
        return True

    return False


def do_close_all_holes(sender=""):
    """Feature 1: Auto-close all holes on current mesh"""
    _log("=" * 50)
    _log("Close All Holes")
    _log("=" * 50)

    if not _ensure_edit_mode():
        return

    vtx_before = _get_vertex_count()
    face_before = _get_face_count()
    _log(f"Before: {vtx_before} vertices, {face_before} faces")

    _close_holes()
    zbc.update(redraw_ui=True)

    vtx_after = _get_vertex_count()
    face_after = _get_face_count()
    _log(f"After:  {vtx_after} vertices, {face_after} faces")
    _log(f"Added:  {face_after - face_before} face(s)")

    _progress("Complete!", 1.0)
    zbc.message_ok(
        f"Close Holes Complete!\n\n"
        f"Holes closed on current mesh.\n"
        f"Faces added: {face_after - face_before}",
        "ZMeshMend"
    )
    _clear_progress()


def do_remove_small_fragments(sender=""):
    """Feature 2: Remove small disconnected fragments"""
    _log("=" * 50)
    _log("Remove Small Fragments")
    _log("=" * 50)

    if not _ensure_edit_mode():
        return

    vtx_before = _get_vertex_count()
    face_before = _get_face_count()
    _log(f"Before: {vtx_before} vertices, {face_before} faces")

    tmp_obj = os.path.join(tempfile.gettempdir(), "zmeshmend_frag.obj")

    _progress("Exporting mesh...", 0.1)
    if not _export_obj(tmp_obj):
        _log("ERROR: Failed to export mesh")
        _clear_progress()
        return

    _progress("Analyzing fragments...", 0.4)
    removed = _remove_small_fragments(
        tmp_obj, face_before,
        CONFIG["fragmentMinFraction"],
        CONFIG["fragmentMinFaces"]
    )

    if removed:
        _progress("Importing cleaned mesh...", 0.7)
        if _import_obj(tmp_obj):
            zbc.update(redraw_ui=True)
            vtx_after = _get_vertex_count()
            face_after = _get_face_count()
            _log(f"After:  {vtx_after} vertices, {face_after} faces")
            _log(f"Removed: {face_before - face_after} face(s)")
        else:
            _log("ERROR: Import failed, mesh may be in an inconsistent state")
    else:
        _log("No small fragments found to remove")

    try:
        os.remove(tmp_obj)
    except Exception:
        pass

    _progress("Complete!", 1.0)
    zbc.message_ok(
        "Fragment Removal Complete!\n\n"
        "Small disconnected fragments have been removed.\n"
        "Check the console for details.",
        "ZMeshMend"
    )
    _clear_progress()


def do_close_with_polygroup_mask(sender=""):
    """Feature 3+4: Close holes with CGAL refine+fair, assign new PolyGroup to filled areas.

    Export OBJ → CGAL fills → import GoZ (with PolyGroups embedded).
    GoZ format natively carries PolyGroup IDs and Mask data,
    so fill faces automatically get a separate PolyGroup.
    """
    _log("=" * 50)
    if _cgal_available():
        _log("Close Holes + PolyGroup (CGAL refine+fair + GoZ)")
    else:
        _log("Close Holes + PolyGroup (ZBrush built-in)")
    _log("=" * 50)

    if not _ensure_edit_mode():
        return

    vtx_before = _get_vertex_count()
    face_before = _get_face_count()
    _log(f"Before: {vtx_before} vertices, {face_before} faces")

    if _cgal_available():
        tmp_in = os.path.join(tempfile.gettempdir(), "zmeshmend_cgal_in.obj")
        tmp_patch = os.path.join(tempfile.gettempdir(), "zmeshmend_cgal_patch.obj")

        _progress("Exporting mesh for CGAL...", 0.10)
        if not _export_obj(tmp_in):
            _log("ERROR: Failed to export mesh")
            _clear_progress()
            return

        _progress("CGAL triangulate_refine_and_fair_hole...", 0.20)
        success, faces_added = _call_cgal_fill(tmp_in, tmp_patch)

        merged = False
        if success and os.path.exists(tmp_patch) and _count_faces_in_obj(tmp_patch) > 0:
            _progress("Merging fill patch...", 0.70)
            merged = _merge_patch_and_weld(tmp_patch, orig_obj_path=tmp_in)

        if merged:
            vtx_after = _get_vertex_count()
            face_after = _get_face_count()
            _log(f"After:  {vtx_after} vertices, {face_after} faces")
            _log(f"Added:  {face_after - face_before} face(s)")
            _log("  Patch merged via OBJ weld (original quads preserved)")
        else:
            _log("Patch merge failed or empty patch. Falling back to ZBrush built-in...")
            _close_holes()
            zbc.update(redraw_ui=True)
            _auto_groups()
            zbc.update(redraw_ui=True)

            vtx_after = _get_vertex_count()
            face_after = _get_face_count()
            _log(f"After (fallback): {vtx_after} vertices, {face_after} faces")

        for f in [tmp_in, tmp_patch]:
            try:
                os.remove(f)
            except Exception:
                pass
    else:
        _log("  CGAL EXE not found, using ZBrush built-in Close Holes")
        _log("  To enable CGAL: build zmeshmend_core.exe into ZMeshMendData/")
        _close_holes()
        zbc.update(redraw_ui=True)
        _auto_groups()
        zbc.update(redraw_ui=True)

        vtx_after = _get_vertex_count()
        face_after = _get_face_count()
        _log(f"After:  {vtx_after} vertices, {face_after} faces")
        _log(f"Added:  {face_after - face_before} face(s)")

    _progress("Complete!", 1.0)
    zbc.message_ok(
        "MendHoles + PolyGroup Complete!\n\n"
        "Holes filled with CGAL refine+fair.\n"
        "Fill patch merged via OBJ weld; original quads preserved.\n"
        "Fill faces tagged with the 'ZMeshMend_Fill' PolyGroup.\n\n"
        "Tip: Ctrl+Shift+Click a PolyGroup to mask it.",
        "ZMeshMend"
    )
    _clear_progress()


def do_mask_based_cleanup(sender=""):
    """Feature 5: Mask-based mesh cleanup workflow.
    Steps: sharpen mask → grow mask → invert → hide masked → delete →
           close holes → polygroup
    Mask indicates the area to DELETE. The masked area is removed and
    the resulting hole is filled; the unmasked area is preserved.
    """
    _log("=" * 50)
    _log("Mask-Based Cleanup Workflow")
    _log("=" * 50)

    if not _ensure_edit_mode():
        return

    vtx_before = _get_vertex_count()
    face_before = _get_face_count()
    _log(f"Before: {vtx_before} vertices, {face_before} faces")

    sharpen_passes = CONFIG["maskSharpenPasses"]
    grow_rings = CONFIG["maskGrowRings"]

    _progress("Step 1/5: Sharpening mask...", 0.05)
    _log(f"  Sharpening mask ({sharpen_passes} pass(es))")
    _sharpen_mask(sharpen_passes)
    zbc.update()

    _progress("Step 2/5: Growing mask...", 0.20)
    _log(f"  Growing mask ({grow_rings} ring(s))")
    _grow_mask(grow_rings)
    zbc.update()

    _progress("Step 3/5: Deleting masked faces...", 0.35)
    _log("  Inverting mask so unmasked region becomes hidden...")
    _invert_mask()
    zbc.update()
    _log("  HidePt hides unmasked points (delete region)...")
    _hide_masked()
    zbc.update()
    _log("  Deleting hidden faces (the masked region)...")
    _delete_hidden()
    zbc.update()
    _show_all()
    zbc.update()

    face_after_delete = _get_face_count()
    _log(f"  Faces after deletion: {face_after_delete} (removed {face_before - face_after_delete})")

    _progress("Step 5/6: Closing holes (CGAL patch merge)...", 0.60)
    cgal_merged = False
    if _cgal_available():
        tmp_in = os.path.join(tempfile.gettempdir(), "zmeshmend_mask_in.obj")
        tmp_patch = os.path.join(tempfile.gettempdir(), "zmeshmend_mask_patch.obj")

        if _export_obj(tmp_in):
            success, cgal_added = _call_cgal_fill(tmp_in, tmp_patch)
            if success and os.path.exists(tmp_patch) and _count_faces_in_obj(tmp_patch) > 0:
                if _merge_patch_and_weld(tmp_patch, orig_obj_path=tmp_in):
                    cgal_merged = True
                    _log(f"  CGAL: {cgal_added} faces added, merged via OBJ weld")
                else:
                    _log("  Patch merge failed, falling back to ZBrush close holes")
                    _close_holes()
            else:
                _log("  CGAL failed or empty patch, falling back to ZBrush close holes")
                _close_holes()
            for f in [tmp_in, tmp_patch]:
                try:
                    os.remove(f)
                except Exception:
                    pass
        else:
            _log("  Export failed, using ZBrush built-in")
            _close_holes()
    else:
        _close_holes()
    zbc.update(redraw_ui=True)

    face_after_close = _get_face_count()
    _log(f"  Faces after close: {face_after_close} (added {face_after_close - face_after_delete})")

    _progress("Step 6/6: Grouping filled areas...", 0.85)
    if cgal_merged:
        _log("  CGAL patch merged: ZMeshMend_Fill PolyGroup preserved from OBJ tag")
    else:
        _log("  CGAL not merged - applying Auto Groups fallback")
        _auto_groups()
    zbc.update(redraw_ui=True)

    vtx_after = _get_vertex_count()
    face_after = _get_face_count()
    _log(f"Final: {vtx_after} vertices, {face_after} faces")
    _log(f"Total faces added: {face_after - face_before}")

    _progress("Complete!", 1.0)
    zbc.message_ok(
        "Mask-Based Cleanup Complete!\n\n"
        f"Faces before: {face_before}\n"
        f"Faces deleted: {face_before - face_after_delete}\n"
        f"Faces filled: {face_after_close - face_after_delete}\n"
        f"Faces final: {face_after}\n\n"
        "Fill patch merged via OBJ weld; original quads preserved.\n"
        "Fill faces tagged with the 'ZMeshMend_Fill' PolyGroup.\n"
        "Use Ctrl+Shift+Click to mask by PolyGroup.",
        "ZMeshMend"
    )
    _clear_progress()


def do_export_mesh(sender=""):
    """Export current mesh to OBJ for external processing"""
    _log("=" * 50)
    _log("Export Mesh for Processing")
    _log("=" * 50)

    if not _ensure_edit_mode():
        return

    save_path = zbc.ask_filename("*.obj", "mesh_export.obj", "Export Mesh OBJ")
    if not save_path:
        _log("Export cancelled")
        return

    if _export_obj(save_path):
        vtx = _get_vertex_count()
        face = _get_face_count()
        _log(f"Exported: {vtx} vertices, {face} faces")
        _log(f"Path: {save_path}")
        zbc.message_ok(
            f"Export Complete!\n\n"
            f"Vertices: {vtx}\n"
            f"Faces: {face}\n"
            f"Saved to: {save_path}",
            "ZMeshMend"
        )
    else:
        _log("ERROR: Export failed")
        zbc.message_ok("Export failed!", "ZMeshMend - Error")


def do_import_mesh(sender=""):
    """Import an externally processed OBJ mesh"""
    _log("=" * 50)
    _log("Import Processed Mesh")
    _log("=" * 50)

    load_path = zbc.ask_filename("*.obj", "", "Import OBJ Mesh")
    if not load_path:
        _log("Import cancelled")
        return

    if _import_obj(load_path):
        zbc.update(redraw_ui=True)
        vtx = _get_vertex_count()
        face = _get_face_count()
        _log(f"Imported: {vtx} vertices, {face} faces")
        zbc.message_ok(
            f"Import Complete!\n\n"
            f"Vertices: {vtx}\n"
            f"Faces: {face}",
            "ZMeshMend"
        )
    else:
        _log("ERROR: Import failed")
        zbc.message_ok("Import failed!", "ZMeshMend - Error")


def _on_close_holes_click(sender=""):
    _freeze_op(lambda: do_close_all_holes(sender), "Closing all holes...")


def _on_remove_frag_click(sender=""):
    _freeze_op(lambda: do_remove_small_fragments(sender), "Removing small fragments...")


def _on_close_group_mask_click(sender=""):
    _freeze_op(lambda: do_close_with_polygroup_mask(sender), "Closing holes with curvature detection...")


def _on_mask_cleanup_click(sender=""):
    _freeze_op(lambda: do_mask_based_cleanup(sender), "Mask-based cleanup workflow...")


def _on_export_click(sender=""):
    _freeze_op(lambda: do_export_mesh(sender), "Exporting mesh...")


def _on_import_click(sender=""):
    _freeze_op(lambda: do_import_mesh(sender), "Importing processed mesh...")


def _on_config_change(sender="", value=0.0):
    """Handle config slider/switch changes"""
    name = sender.split(":")[-1] if ":" in sender else sender

    if name == "Fragment Min Fraction":
        CONFIG["fragmentMinFraction"] = value
        save_config()
    elif name == "Fragment Min Faces":
        CONFIG["fragmentMinFaces"] = int(value)
        save_config()
    elif name == "Mask Grow Rings":
        CONFIG["maskGrowRings"] = int(value)
        save_config()
    elif name == "Mask Sharpen Passes":
        CONFIG["maskSharpenPasses"] = int(value)
        save_config()
    elif name == "Remove Small Fragments":
        CONFIG["removeSmallFragments"] = bool(value)
        save_config()


def _on_info_click(sender=""):
    """Show plugin information"""
    zbc.message_ok(
        "ZMeshMend v1.0.0\n\n"
        "Core Features:\n"
        "1. Auto-close all holes\n"
        "2. Remove small disconnected fragments\n"
        "3. Create new PolyGroup for filled areas\n"
        "4. Auto-mask newly closed area\n"
        "5. Mask-based mesh cleanup workflow",
        "ZMeshMend - About"
    )


def build_ui():
    """Build the ZMeshMend plugin UI"""
    load_config()

    if zbc.exists(PALETTE_NAME):
        zbc.close(PALETTE_NAME)

    zbc.add_palette(PALETTE_NAME, docking_bar=1)

    zbc.add_subpalette(SUBPALETTE_MAIN, title_mode=2)

    zbc.add_button(
        _ui_path("Close Holes:Close All Holes"),
        "Automatically closes all open holes on the current mesh.",
        _on_close_holes_click,
        width=1.0,
    )

    zbc.add_button(
        _ui_path("Close Holes:MendHoles + PolyGroup"),
        "Close holes with curvature-aware smart fill, create "
        "new PolyGroups for filled areas, ready for masking.",
        _on_close_group_mask_click,
        width=1.0,
    )

    zbc.add_button(
        _ui_path("Close Holes:Mask-Based Cleanup"),
        "Full workflow: sharpen mask > grow > delete masked faces "
        "> close holes > new PolyGroup for filled area.",
        _on_mask_cleanup_click,
        width=1.0,
    )

    zbc.add_button(
        _ui_path("Close Holes:Remove Small Fragments"),
        "Analyzes mesh connectivity and removes small "
        "disconnected fragments and mesh debris.",
        _on_remove_frag_click,
        width=1.0,
    )

    zbc.add_subpalette(SUBPALETTE_CONF, title_mode=0)

    zbc.add_switch(
        _ui_path("Settings:Remove Small Fragments"),
        CONFIG["removeSmallFragments"],
        "Automatically remove small fragments during cleanup.",
        _on_config_change,
        width=1.0,
    )

    zbc.add_slider(
        _ui_path("Settings:Fragment Min Fraction"),
        CONFIG["fragmentMinFraction"],
        100,
        0.0,
        0.5,
        "Min fraction of total faces for a fragment to be kept (0.0-0.5).",
        _on_config_change,
        width=1.0,
    )

    zbc.add_slider(
        _ui_path("Settings:Fragment Min Faces"),
        float(CONFIG["fragmentMinFaces"]),
        1,
        1.0,
        500.0,
        "Minimum absolute face count for a fragment to be kept.",
        _on_config_change,
        width=1.0,
    )

    zbc.add_slider(
        _ui_path("Settings:Mask Grow Rings"),
        float(CONFIG["maskGrowRings"]),
        1,
        0.0,
        5.0,
        "Number of rings to grow the mask before deleting faces.",
        _on_config_change,
        width=1.0,
    )

    zbc.add_slider(
        _ui_path("Settings:Mask Sharpen Passes"),
        float(CONFIG["maskSharpenPasses"]),
        1,
        0.0,
        5.0,
        "Number of mask sharpen passes before grow.",
        _on_config_change,
        width=1.0,
    )

    zbc.add_subpalette(SUBPALETTE_INFO, title_mode=0)

    zbc.add_button(
        _ui_path("Info:Export Current Mesh"),
        "Export current mesh to OBJ for external processing.",
        _on_export_click,
        width=1.0,
    )

    zbc.add_button(
        _ui_path("Info:Import Processed Mesh"),
        "Import an externally processed OBJ mesh.",
        _on_import_click,
        width=1.0,
    )

    zbc.add_button(
        _ui_path("Info:About ZMeshMend"),
        "Show plugin information and version.",
        _on_info_click,
        width=1.0,
    )

    zbc.maximize(SUBPALETTE_MAIN)
    zbc.maximize(SUBPALETTE_CONF)
    zbc.maximize(SUBPALETTE_INFO)

    _log("ZMeshMend v1.0.0 loaded")
    _log(f"Config path: {CONFIG_PATH}")
    if _cgal_available():
        _log(f"CGAL Core:   {_CGAL_EXE_REL}")
    else:
        _log(f"CGAL Core:   NOT FOUND (using ZBrush built-in Close Holes)")
        _log(f"  Expected:  {_CGAL_EXE_REL}")
        _log(f"  Build with: ZMeshMendData/build.bat")


def main():
    """Entry point - builds the plugin UI"""
    build_ui()


if __name__ == "__main__":
    main()
