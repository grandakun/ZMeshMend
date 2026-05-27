"""ZMeshMend Plugin - Auto-Load Initialization

Place the parent directory of this file in your PYTHONPATH or
ZBRUSH_PLUGIN_PATH environment variable to auto-load the plugin
when ZBrush starts.

Alternatively, load ZMeshMend.py directly via ZScript > Python Scripting > Load.
"""

import os
import sys

_script_dir = os.path.dirname(os.path.abspath(__file__))
if _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)

from ZMeshMend import main as _main

_main()
