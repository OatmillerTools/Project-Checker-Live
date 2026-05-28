"""Runtime hook: add bundled Tcl9-compatible tkdnd to Tcl auto_path before tkinterdnd2 loads."""
import os
import sys

if getattr(sys, 'frozen', False):
    _tkdnd9_dir = os.path.join(sys._MEIPASS, 'tkdnd9')
    if os.path.isdir(_tkdnd9_dir):
        # Patch TkinterDnD._require to prepend our Tcl9 dir before calling package require
        import tkinterdnd2.TkinterDnD as _tdn

        _orig_require = _tdn._require

        def _patched_require(tkroot):
            tkroot.tk.call('lappend', 'auto_path', _tkdnd9_dir)
            return _orig_require(tkroot)

        _tdn._require = _patched_require
