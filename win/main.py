import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
from tkinterdnd2 import TkinterDnD, DND_FILES

from als_parser import parse_als, scan_vst_plugins

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ── Colors ─────────────────────────────────────────────────────────────────────
C_OK    = "#4CAF50"
C_WARN  = "#FFA726"
C_ERR   = "#EF5350"
C_MUTED = "#888888"
C_LABEL = "#AAAAAA"
C_VALUE = "#E0E0E0"
C_HEADER= "#FFFFFF"
C_VST    = "#FFD54F"
C_M4L    = "#CE93D8"
C_SILENT = "#78909C"   # blue-grey — fader at -∞ (muted/off)
C_BG_CARD = "#2B2B2B"
C_BG_ALT  = "#333333"

_SILENT_THRESHOLD = -64.0

# Native MIDI-effect display names (stored under live_instruments in parser)
_MIDI_FX_NAMES = {
    "Arpeggiator", "Chord", "Note Length", "Pitch",
    "Random", "Scale", "Velocity", "MIDI Monitor", "CC Control",
}

# Rack display name prefixes (used to filter them from flat instrument/effect lists)
_RACK_PREFIXES = (
    "Instrument Rack", "Audio Effect Rack", "Drum Rack", "MIDI Effect Rack",
)

_TYPE_COLORS = {
    "midi": "#64B5F6", "audio": "#81C784",
    "group": "#FFD54F", "return": "#CE93D8", "main": "#FF8A65",
}


def _is_rack_entry(name: str) -> bool:
    return any(name.startswith(p) for p in _RACK_PREFIXES)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _fmt_db(val) -> str:
    if val is None:
        return "—"
    if val == float("-inf") or val <= _SILENT_THRESHOLD:
        return "-∞ dB"
    sign = "+" if val > 0 else ""
    return f"{sign}{val:.1f} dB"


def _db_color(val) -> str:
    """Color for a fader dB value shown on a track."""
    if val is None:
        return C_MUTED
    if val == float("-inf") or val <= _SILENT_THRESHOLD:
        return C_SILENT
    if val > 0:
        return C_WARN
    return C_VALUE


def _track_type_label(t: str) -> str:
    return {"midi": "MIDI", "audio": "Audio", "group": "Group", "return": "Return"}.get(t, t)


def _join_m4l(names: list[str]) -> str:
    return ", ".join(f"{n} [M4L]" for n in names)


def _arr_str(arr: dict | None) -> str:
    if not arr:
        return "—"
    t = arr["time_str"].split(":")
    return f"{t[0]}:{t[1][:2]} / {arr['bars']:.0f} bars @ {arr['bpm']} BPM"


def _ru_chains(n: int) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return f"{n} цепочка"
    if 2 <= n % 10 <= 4 and not (12 <= n % 100 <= 14):
        return f"{n} цепочки"
    return f"{n} цепочек"


def _rack_devices(rack_details: list, mode: str) -> list[str]:
    """Recursively collect device names from rack_details for tab lists."""
    names: list[str] = []
    for rack in rack_details:
        for chain in rack.get("chains", []):
            if mode == "instruments":
                names.extend(n for n in chain.get("live_instruments", [])
                             if not _is_rack_entry(n) and n not in _MIDI_FX_NAMES)
                names.extend(f"{n} [M4L]" for n in chain.get("m4l_instruments", []))
            elif mode == "audiofx":
                names.extend(n for n in chain.get("live_effects", []) if not _is_rack_entry(n))
                names.extend(f"{n} [M4L]" for n in chain.get("m4l_effects", []))
            elif mode == "midifx":
                names.extend(n for n in chain.get("live_instruments", []) if n in _MIDI_FX_NAMES)
                names.extend(f"{n} [M4L]" for n in chain.get("m4l_midi", []))
            elif mode == "vst":
                names.extend(f"VST2: {v}" for v in chain.get("vst2", []))
                names.extend(f"VST3: {v}" for v in chain.get("vst3", []))
            names.extend(_rack_devices(chain.get("rack_details", []), mode))
    return names


def _build_report(data: dict) -> str:
    lines = ["Ableton Project Checker Report", f"Version: {data['ableton_version']}", ""]

    arr = data.get("arrangement")
    if arr:
        lines.append(f"Длина аранжировки: {_arr_str(arr)}")
        lines.append("")

    main = data["main"]
    lines.append("=== MAIN КАНАЛ ===")
    lines.append(f"  Фейдер: {_fmt_db(main['fader_db'])}")
    if main["fader_above_0db"]:
        lines.append("  ⚠ ВНИМАНИЕ: фейдер выше 0 dB!")
    if main["live_effects"]:
        lines.append(f"  Эффекты Live: {', '.join(main['live_effects'])}")
    if main["vst2_plugins"]:
        lines.append(f"  VST2: {', '.join(main['vst2_plugins'])}")
    if main["vst3_plugins"]:
        lines.append(f"  VST3: {', '.join(main['vst3_plugins'])}")
    if main["m4l_effects"]:
        lines.append(f"  M4L: {', '.join(main['m4l_effects'])}")
    lines.append("")

    lines.append("=== ТРЕКИ ===")
    for tr in data["tracks"]:
        mute_tag = "  [MUTED]" if tr.get("is_muted") else ""
        lines.append(
            f"[{_track_type_label(tr['type'])}] {tr['name']}  |  {_fmt_db(tr['fader_db'])}{mute_tag}"
        )
        if not tr["has_content"]:
            lines.append("  — Нет контента (клипы пустые)")
        else:
            if tr["live_instruments"]:
                lines.append(f"  Инструменты: {', '.join(tr['live_instruments'])}")
            if tr["m4l_instruments"]:
                lines.append(f"  Инструменты M4L: {', '.join(tr['m4l_instruments'])}")
            if tr["live_effects"]:
                lines.append(f"  Эффекты: {', '.join(tr['live_effects'])}")
            if tr["m4l_effects"]:
                lines.append(f"  Эффекты M4L: {', '.join(tr['m4l_effects'])}")
            if tr["m4l_midi"]:
                lines.append(f"  MIDI M4L: {', '.join(tr['m4l_midi'])}")
            if tr["vst2_plugins"]:
                lines.append(f"  VST2: {', '.join(tr['vst2_plugins'])}")
            if tr["vst3_plugins"]:
                lines.append(f"  VST3: {', '.join(tr['vst3_plugins'])}")
            lines.append(f"  Автоматизация: {'Да' if tr['has_automation'] else 'Нет'}")
            for s in tr.get("sends", []):
                suffix = "" if s["active"] else " [откл.]"
                lines.append(f"  Send {s['name']}: {_fmt_db(s['db'])}{suffix}")
    lines.append("")

    with_content = [t for t in data["tracks"] if t["has_content"]]
    vst_total: set[str] = set()
    auto_count = sum(1 for t in data["tracks"] if t["has_automation"])
    for t in data["tracks"]:
        vst_total.update(t["vst2_plugins"])
        vst_total.update(t["vst3_plugins"])
    vst_total.update(main["vst2_plugins"])
    vst_total.update(main["vst3_plugins"])

    lines.append("=== СВОДКА ===")
    lines.append(f"  Треков: {len(data['tracks'])}  |  с контентом: {len(with_content)}")
    lines.append(f"  Сторонних плагинов (уникальных): {len(vst_total)}")
    lines.append(f"  Треков с автоматизацией: {auto_count}")

    samples = data.get("samples", {})
    missing = samples.get("missing", [])
    found   = samples.get("found", [])
    if found or missing:
        lines.append(f"  Семплы: найдено {len(found)}, не найдено {len(missing)}")
        if missing:
            lines.append(f"  Отсутствуют: {', '.join(missing)}")

    return "\n".join(lines)


# ── UI components ──────────────────────────────────────────────────────────────

class SectionLabel(ctk.CTkLabel):
    def __init__(self, master, text, **kw):
        super().__init__(master, text=text, font=("Segoe UI", 13, "bold"),
                         text_color=C_HEADER, **kw)


class KVRow(ctk.CTkFrame):
    def __init__(self, master, key: str, value: str, value_color: str = C_VALUE, **kw):
        super().__init__(master, fg_color="transparent", **kw)
        ctk.CTkLabel(self, text=key, font=("Segoe UI", 11), text_color=C_LABEL,
                     width=160, anchor="w").pack(side="left")
        ctk.CTkLabel(self, text=value, font=("Segoe UI", 11, "bold"),
                     text_color=value_color, anchor="w").pack(side="left", padx=(4, 0))


class ExpandableRack(ctk.CTkFrame):
    """Collapsible widget showing a rack's chain contents."""

    def __init__(self, master, rack: dict, **kw):
        super().__init__(master, fg_color="transparent", **kw)
        self._expanded = False
        chains = rack.get("chains", [])
        n = len(chains)
        rack_type = rack["rack_type"]
        self._lbl_collapsed = f"▶  {rack_type}  ({_ru_chains(n)})"
        self._lbl_expanded  = f"▼  {rack_type}  ({_ru_chains(n)})"

        self._btn = ctk.CTkButton(
            self, text=self._lbl_collapsed, command=self._toggle,
            fg_color="#383838", hover_color="#464646",
            anchor="w", font=("Segoe UI", 11), text_color=C_VALUE, height=28,
        )
        self._btn.pack(fill="x", pady=(2, 0))

        self._inner = ctk.CTkFrame(self, fg_color="#232323", corner_radius=4)
        for ch in chains:
            self._build_chain(self._inner, ch)

    def _build_chain(self, parent: ctk.CTkFrame, chain: dict):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.pack(fill="x", padx=10, pady=(4, 0))
        name = chain.get("chain_name", "").strip()
        if name:
            ctk.CTkLabel(f, text=name, font=("Segoe UI", 10, "bold"),
                         text_color=C_LABEL).pack(anchor="w")
        devs: list[str] = []
        devs.extend(chain.get("live_instruments", []))
        devs.extend(chain.get("live_effects", []))
        for v in chain.get("vst2", []):
            devs.append(f"VST2: {v}")
        for v in chain.get("vst3", []):
            devs.append(f"VST3: {v}")
        for m in chain.get("m4l_instruments", []) + chain.get("m4l_effects", []):
            devs.append(f"{m} [M4L]")
        if devs:
            ctk.CTkLabel(f, text="  " + " → ".join(devs),
                         font=("Segoe UI", 10), text_color=C_VALUE,
                         wraplength=480, justify="left").pack(anchor="w")
        ctk.CTkFrame(parent, fg_color="#383838", height=1).pack(fill="x", padx=10, pady=3)

    def _toggle(self):
        if self._expanded:
            self._inner.pack_forget()
            self._btn.configure(text=self._lbl_collapsed)
        else:
            self._inner.pack(fill="x", pady=(0, 4))
            self._btn.configure(text=self._lbl_expanded)
        self._expanded = not self._expanded


class ExpandableSamples(ctk.CTkFrame):
    """Expandable card showing sample collect-all status."""

    def __init__(self, master, samples: dict, **kw):
        found   = samples.get("found", [])
        missing = samples.get("missing", [])
        total   = len(found) + len(missing)

        if missing:
            bg, text_col = "#2E1A1A", C_ERR
            summary = (f"⚠  Семплы: {len(found)} из {total} в папке проекта  "
                       f"— {len(missing)} отсутствуют")
        elif total == 0:
            bg, text_col = "#1A2E1A", C_OK
            summary = "✓  Семплы не используются"
        else:
            bg, text_col = "#1A2E1A", C_OK
            summary = f"✓  Все семплы в папке проекта  ({total})"

        super().__init__(master, fg_color=bg, corner_radius=8, **kw)
        self._expanded = False
        self._summary  = summary
        self._text_col = text_col

        if total == 0:
            ctk.CTkLabel(self, text=summary, font=("Segoe UI", 11),
                         text_color=text_col, justify="left").pack(anchor="w", padx=12, pady=8)
            return

        self._btn = ctk.CTkButton(
            self, text=f"▶  {summary}", command=self._toggle,
            fg_color="transparent", hover_color="#404040",
            anchor="w", font=("Segoe UI", 11), text_color=text_col, height=34,
        )
        self._btn.pack(fill="x", padx=4, pady=2)

        self._inner = ctk.CTkFrame(self, fg_color="transparent")
        for name in found:
            self._sample_row(self._inner, "✓", name, C_OK)
        for name in missing:
            self._sample_row(self._inner, "✗", name, C_ERR)
        ctk.CTkFrame(self._inner, fg_color="transparent", height=4).pack()

    @staticmethod
    def _sample_row(parent, icon: str, name: str, color: str):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.pack(fill="x", padx=16, pady=1)
        ctk.CTkLabel(f, text=icon, font=("Segoe UI", 11, "bold"),
                     text_color=color, width=18).pack(side="left")
        ctk.CTkLabel(f, text=name, font=("Segoe UI", 11),
                     text_color=color, anchor="w").pack(side="left", padx=(4, 0))

    def _toggle(self):
        if self._expanded:
            self._inner.pack_forget()
            self._btn.configure(text=f"▶  {self._summary}")
        else:
            self._inner.pack(fill="x")
            self._btn.configure(text=f"▼  {self._summary}")
        self._expanded = not self._expanded


class TrackCard(ctk.CTkFrame):
    def __init__(self, master, track: dict, index: int, **kw):
        bg = "#2E1A1A" if not track["has_content"] else (
            C_BG_CARD if index % 2 == 0 else C_BG_ALT
        )
        super().__init__(master, fg_color=bg, corner_radius=6, **kw)
        self._build(track)

    def _build(self, tr: dict):
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=10, pady=(8, 2))

        tc = _TYPE_COLORS.get(tr["type"], C_VALUE)
        ctk.CTkLabel(top, text=f"[{_track_type_label(tr['type'])}]",
                     font=("Segoe UI", 11, "bold"), text_color=tc).pack(side="left")
        ctk.CTkLabel(top, text=f"  {tr['name']}",
                     font=("Segoe UI", 12, "bold"), text_color=C_HEADER).pack(side="left")
        ctk.CTkLabel(top, text=f"  {_fmt_db(tr['fader_db'])}",
                     font=("Segoe UI", 11), text_color=_db_color(tr["fader_db"])).pack(side="left")
        if tr.get("is_muted"):
            ctk.CTkLabel(top, text="  MUTED",
                         font=("Segoe UI", 11, "bold"), text_color=C_WARN).pack(side="left")

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="x", padx=14, pady=(0, 8))

        if not tr["has_content"]:
            ctk.CTkLabel(body, text="— Нет контента (клипы пустые)",
                         font=("Segoe UI", 11), text_color=C_MUTED).pack(anchor="w")
            return

        # Flat device lists (racks shown separately as expandable widgets)
        plain_instr = [n for n in tr["live_instruments"]
                       if not _is_rack_entry(n) and n not in _MIDI_FX_NAMES]
        plain_fx    = [n for n in tr["live_effects"] if not _is_rack_entry(n)]

        if plain_instr:
            self._row(body, "Инструменты Live:", ", ".join(plain_instr), C_VALUE)
        if tr["m4l_instruments"]:
            self._row(body, "Инструменты M4L:", _join_m4l(tr["m4l_instruments"]), C_M4L)
        if plain_fx:
            self._row(body, "Эффекты Live:", ", ".join(plain_fx), C_VALUE)
        if tr["m4l_effects"]:
            self._row(body, "Эффекты M4L:", _join_m4l(tr["m4l_effects"]), C_M4L)
        if tr["m4l_midi"]:
            self._row(body, "MIDI-эффекты M4L:", _join_m4l(tr["m4l_midi"]), C_M4L)
        if tr["vst2_plugins"]:
            self._row(body, "VST2:", ", ".join(tr["vst2_plugins"]), C_VST)
        if tr["vst3_plugins"]:
            self._row(body, "VST3:", ", ".join(tr["vst3_plugins"]), C_VST)

        for rack in tr.get("rack_details", []):
            ExpandableRack(body, rack).pack(fill="x", pady=(2, 0))

        auto_col = C_OK if tr["has_automation"] else C_MUTED
        self._row(body, "Автоматизация:", "Есть" if tr["has_automation"] else "Нет", auto_col)

        for s in tr.get("sends", []):
            suffix = "" if s["active"] else "  [откл.]"
            self._row(body, f"  Send {s['name']}:",
                      _fmt_db(s["db"]) + suffix, _db_color(s["db"]))

    @staticmethod
    def _row(parent, key: str, value: str, color: str):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.pack(anchor="w", fill="x")
        ctk.CTkLabel(f, text=key, font=("Segoe UI", 11), text_color=C_LABEL,
                     width=160, anchor="w").pack(side="left")
        ctk.CTkLabel(f, text=value, font=("Segoe UI", 11),
                     text_color=color, anchor="w", wraplength=520, justify="left").pack(
            side="left", padx=(4, 0))


# ── Main window ────────────────────────────────────────────────────────────────

class App(ctk.CTk, TkinterDnD.DnDWrapper):
    def __init__(self):
        super().__init__()
        self.TkdndVersion = TkinterDnD._require(self)
        self.title("Ableton Project Checker")
        self.geometry("900x760")
        self.minsize(720, 540)
        self._data = None
        self._vst_scan = None
        self._content_shown = False
        self._build_ui()
        self._setup_dnd()

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="#1E1E1E", corner_radius=0)
        header.pack(fill="x")
        ctk.CTkLabel(header, text="Ableton Project Checker",
                     font=("Segoe UI", 16, "bold"), text_color=C_HEADER).pack(
            side="left", padx=16, pady=12)
        self._btn_open = ctk.CTkButton(header, text="Открыть .als файл",
                                       command=self._open_file, width=160)
        self._btn_open.pack(side="right", padx=12, pady=10)
        self._btn_copy = ctk.CTkButton(header, text="Копировать отчёт",
                                       command=self._copy_report, width=160,
                                       fg_color="#555555", hover_color="#666666")
        self._btn_copy.pack(side="right", padx=(0, 4), pady=10)
        self._btn_copy.configure(state="disabled")

        self._file_bar = ctk.CTkFrame(self, fg_color="#252525", corner_radius=0)
        self._file_bar.pack(fill="x")
        self._lbl_file = ctk.CTkLabel(self._file_bar, text="Файл не выбран",
                                      font=("Segoe UI", 11), text_color=C_MUTED)
        self._lbl_file.pack(side="left", padx=16, pady=6)
        self._lbl_version = ctk.CTkLabel(self._file_bar, text="",
                                         font=("Segoe UI", 11), text_color=C_MUTED)
        self._lbl_version.pack(side="right", padx=16, pady=6)

        # Content container: info_area (fixed top) + tabview (expanding bottom)
        self._content = ctk.CTkFrame(self, fg_color="#1A1A1A", corner_radius=0)
        self._info_area = ctk.CTkFrame(self._content, fg_color="#1A1A1A", corner_radius=0)
        self._info_area.pack(fill="x")

        self._placeholder = ctk.CTkLabel(
            self,
            text="Перетащите .als файл сюда\nили нажмите «Открыть .als файл»",
            font=("Segoe UI", 14), text_color=C_MUTED, justify="center",
        )
        self._placeholder.pack(fill="both", expand=True)

    def _setup_dnd(self):
        self.drop_target_register(DND_FILES)
        self.dnd_bind("<<Drop>>",      self._on_drop)
        self.dnd_bind("<<DragEnter>>", self._on_drag_enter)
        self.dnd_bind("<<DragLeave>>", self._on_drag_leave)

    def _on_drag_enter(self, event):
        self._file_bar.configure(fg_color="#1E2A1E")
        if not self._content_shown:
            self._placeholder.configure(fg_color="#1E2A1E")

    def _on_drag_leave(self, event):
        self._file_bar.configure(fg_color="#252525")
        self._placeholder.configure(fg_color="transparent")

    def _on_drop(self, event):
        self._file_bar.configure(fg_color="#252525")
        self._placeholder.configure(fg_color="transparent")
        raw = event.data.strip()
        if raw.startswith("{"):
            raw = raw[1:raw.find("}")]
        else:
            raw = raw.split()[0]
        if not raw.lower().endswith(".als"):
            messagebox.showwarning("Неверный файл", "Пожалуйста, перетащите файл .als")
            return
        self._load_file(raw)

    def _open_file(self):
        path = filedialog.askopenfilename(
            title="Выберите файл Ableton Live",
            filetypes=[("Ableton Live Set", "*.als"), ("Все файлы", "*.*")]
        )
        if path:
            self._load_file(path)

    def _load_file(self, path: str):
        try:
            data = parse_als(path)
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))
            return
        self._data = data
        self._lbl_file.configure(text=os.path.basename(path), text_color=C_VALUE)
        self._lbl_version.configure(text=data["ableton_version"])
        self._btn_copy.configure(state="normal")
        self._render(data)

    def _render(self, data: dict):
        self._vst_scan = None
        for w in self._info_area.winfo_children():
            w.destroy()
        if hasattr(self, "_tabview") and self._tabview.winfo_exists():
            self._tabview.destroy()

        if not self._content_shown:
            self._placeholder.pack_forget()
            self._content.pack(fill="both", expand=True)
            self._content_shown = True

        self._build_info_area(data)

        self._tabview = ctk.CTkTabview(
            self._content, fg_color="#1E1E1E", corner_radius=0,
            segmented_button_fg_color="#2B2B2B",
            segmented_button_selected_color="#3A3A5A",
            segmented_button_selected_hover_color="#4A4A6A",
        )
        self._tabview.pack(fill="both", expand=True)
        for name in ["Треки", "Инструменты", "Аудио FX", "MIDI FX", "VST"]:
            self._tabview.add(name)

        self._build_tab_tracks(self._tabview.tab("Треки"), data)
        self._build_tab_list(self._tabview.tab("Инструменты"), data, "instruments")
        self._build_tab_list(self._tabview.tab("Аудио FX"),    data, "audiofx")
        self._build_tab_list(self._tabview.tab("MIDI FX"),     data, "midifx")
        self._build_tab_list(self._tabview.tab("VST"),         data, "vst")

    # ── Info area (above tabs) ─────────────────────────────────────────────────

    def _build_info_area(self, data: dict):
        pad = {"padx": 12, "pady": 4}

        main_card = ctk.CTkFrame(self._info_area, fg_color="#252840", corner_radius=8)
        main_card.pack(fill="x", **pad)
        SectionLabel(main_card, "MAIN КАНАЛ").pack(anchor="w", padx=12, pady=(10, 4))

        main = data["main"]
        rf = ctk.CTkFrame(main_card, fg_color="transparent")
        rf.pack(fill="x", padx=12, pady=(0, 4))

        fdb = main["fader_db"]
        fader_txt = _fmt_db(fdb)
        if main["fader_above_0db"]:
            fader_col = C_ERR
            fader_txt += "  ⚠ выше 0 dB!"
        elif fdb is not None and (fdb == float("-inf") or fdb <= _SILENT_THRESHOLD):
            fader_col = C_SILENT
        else:
            fader_col = C_OK
        KVRow(rf, "Фейдер:", fader_txt, fader_col).pack(anchor="w")

        all_main_fx = (main["live_effects"]
                       + [f"[VST2] {p}" for p in main["vst2_plugins"]]
                       + [f"[VST3] {p}" for p in main["vst3_plugins"]])
        KVRow(rf, "Плагины на Main:",
              ", ".join(all_main_fx) if all_main_fx else "Нет",
              C_VALUE if all_main_fx else C_MUTED).pack(anchor="w")
        if main["m4l_effects"]:
            KVRow(rf, "M4L на Main:", _join_m4l(main["m4l_effects"]), C_M4L).pack(anchor="w")
        ctk.CTkFrame(main_card, fg_color="transparent", height=6).pack()

        # Summary bar
        with_content = [t for t in data["tracks"] if t["has_content"]]
        vst_all: set[str] = set()
        for t in data["tracks"]:
            vst_all.update(t["vst2_plugins"]); vst_all.update(t["vst3_plugins"])
        vst_all.update(main["vst2_plugins"]); vst_all.update(main["vst3_plugins"])
        auto_count = sum(1 for t in data["tracks"] if t["has_automation"])

        summary_card = ctk.CTkFrame(self._info_area, fg_color="#263226", corner_radius=8)
        summary_card.pack(fill="x", **pad)
        sf = ctk.CTkFrame(summary_card, fg_color="transparent")
        sf.pack(fill="x", padx=12, pady=8)

        for label, val in [
            ("Треков всего:", str(len(data["tracks"]))),
            ("С контентом:", str(len(with_content))),
            ("Длина:", _arr_str(data.get("arrangement"))),
            ("Сторонних плагинов:", str(len(vst_all))),
            ("Автоматизация на:", f"{auto_count} тр."),
        ]:
            col = ctk.CTkFrame(sf, fg_color="transparent")
            col.pack(side="left", padx=14)
            ctk.CTkLabel(col, text=label, font=("Segoe UI", 10), text_color=C_LABEL).pack()
            ctk.CTkLabel(col, text=val, font=("Segoe UI", 14, "bold"), text_color=C_OK).pack()

        # Samples status — expandable
        ExpandableSamples(
            self._info_area, data.get("samples", {})
        ).pack(fill="x", **pad)

    # ── Tab builders ───────────────────────────────────────────────────────────

    def _build_tab_tracks(self, frame: ctk.CTkFrame, data: dict):
        scroll = ctk.CTkScrollableFrame(frame, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        tracks = data["tracks"]
        by_id = {t["track_id"]: t for t in tracks if t.get("track_id", -1) != -1}

        def _depth(t: dict, _seen: set | None = None) -> int:
            _seen = _seen or set()
            gid = t.get("group_id", -1)
            if gid == -1 or gid in _seen:
                return 0
            _seen.add(gid)
            parent = by_id.get(gid)
            return 1 + (_depth(parent, _seen) if parent else 0)

        for i, track in enumerate(tracks):
            d = _depth(track)
            left_pad = 8 + d * 24
            TrackCard(scroll, track, i).pack(fill="x", padx=(left_pad, 8), pady=2)

        ctk.CTkFrame(scroll, fg_color="transparent", height=12).pack()

    def _build_tab_list(self, frame: ctk.CTkFrame, data: dict, mode: str):
        """Flat list tab. mode: 'instruments' | 'audiofx' | 'midifx' | 'vst'"""
        # rows: (track_name, track_type, dev_display, dev_color)
        rows: list[tuple[str, str, str, str]] = []
        main = data["main"]

        if mode == "instruments":
            for t in data["tracks"]:
                if not t["has_content"]:
                    continue
                for d in t["live_instruments"]:
                    if not _is_rack_entry(d) and d not in _MIDI_FX_NAMES:
                        rows.append((t["name"], t["type"], d, C_VALUE))
                for d in t["m4l_instruments"]:
                    rows.append((t["name"], t["type"], f"{d} [M4L]", C_M4L))
                for d in _rack_devices(t.get("rack_details", []), "instruments"):
                    rows.append((t["name"], t["type"], d, C_VALUE))

        elif mode == "audiofx":
            for t in data["tracks"]:
                if not t["has_content"]:
                    continue
                for d in t["live_effects"]:
                    if not _is_rack_entry(d):
                        rows.append((t["name"], t["type"], d, C_VALUE))
                for d in t["m4l_effects"]:
                    rows.append((t["name"], t["type"], f"{d} [M4L]", C_M4L))
                for d in _rack_devices(t.get("rack_details", []), "audiofx"):
                    col = C_M4L if "[M4L]" in d else C_VALUE
                    rows.append((t["name"], t["type"], d, col))
            for d in main["live_effects"]:
                rows.append(("Main", "main", d, C_VALUE))
            for d in main["m4l_effects"]:
                rows.append(("Main", "main", f"{d} [M4L]", C_M4L))
            for d in _rack_devices(main.get("rack_details", []), "audiofx"):
                col = C_M4L if "[M4L]" in d else C_VALUE
                rows.append(("Main", "main", d, col))

        elif mode == "midifx":
            for t in data["tracks"]:
                if not t["has_content"]:
                    continue
                for d in t["live_instruments"]:
                    if d in _MIDI_FX_NAMES:
                        rows.append((t["name"], t["type"], d, C_VALUE))
                for d in t["m4l_midi"]:
                    rows.append((t["name"], t["type"], f"{d} [M4L]", C_M4L))
                for d in _rack_devices(t.get("rack_details", []), "midifx"):
                    col = C_M4L if "[M4L]" in d else C_VALUE
                    rows.append((t["name"], t["type"], d, col))

        elif mode == "vst":
            for t in data["tracks"]:
                for d in t["vst2_plugins"]:
                    rows.append((t["name"], t["type"], f"VST2: {d}", C_VST))
                for d in t["vst3_plugins"]:
                    rows.append((t["name"], t["type"], f"VST3: {d}", C_VST))
                for d in _rack_devices(t.get("rack_details", []), "vst"):
                    rows.append((t["name"], t["type"], d, C_VST))
            for d in main["vst2_plugins"]:
                rows.append(("Main", "main", f"VST2: {d}", C_VST))
            for d in main["vst3_plugins"]:
                rows.append(("Main", "main", f"VST3: {d}", C_VST))
            for d in _rack_devices(main.get("rack_details", []), "vst"):
                rows.append(("Main", "main", d, C_VST))

            # ── Scan header ────────────────────────────────────────────────────
            hdr = ctk.CTkFrame(frame, fg_color="#1E1E1E", corner_radius=0)
            hdr.pack(fill="x")
            scan_btn = ctk.CTkButton(
                hdr, text="Сканировать плагины",
                command=lambda: self._run_vst_scan(scan_btn, summary_lbl),
                width=180, fg_color="#3A3A5A", hover_color="#4A4A6A",
            )
            scan_btn.pack(side="left", padx=12, pady=8)
            summary_lbl = ctk.CTkLabel(hdr, text="", font=("Segoe UI", 11),
                                       text_color="#888888")
            summary_lbl.pack(side="left", padx=4)
            if self._vst_scan is not None:
                found = sum(1 for v in self._vst_scan.values() if v)
                total = len(self._vst_scan)
                if found == total:
                    summary_lbl.configure(
                        text=f"✓  Все {total} найдены", text_color="#4CAF50")
                else:
                    scol = "#FFA726" if found > 0 else "#EF5350"
                    summary_lbl.configure(
                        text=f"Найдено {found} из {total}  •  {total-found} отсутствуют",
                        text_color=scol)
                scan_btn.configure(text="Обновить")

        scroll = ctk.CTkScrollableFrame(frame, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        if not rows:
            ctk.CTkLabel(scroll, text="Нет", font=("Segoe UI", 13),
                         text_color=C_MUTED).pack(pady=40)
            return

        for i, (track_name, track_type, dev_name, dev_col) in enumerate(rows):
            bg = C_BG_CARD if i % 2 == 0 else C_BG_ALT
            row_f = ctk.CTkFrame(scroll, fg_color=bg, corner_radius=4)
            row_f.pack(fill="x", padx=8, pady=1)
            tc   = _TYPE_COLORS.get(track_type, C_VALUE)
            tag  = _track_type_label(track_type).upper() if track_type != "main" else "MAIN"
            ctk.CTkLabel(row_f, text=f"[{tag}]",
                         font=("Segoe UI", 10, "bold"), text_color=tc,
                         width=55).pack(side="left", padx=(8, 4), pady=5)
            ctk.CTkLabel(row_f, text=track_name,
                         font=("Segoe UI", 11), text_color=C_LABEL,
                         width=180, anchor="w").pack(side="left")
            ctk.CTkLabel(row_f, text=dev_name,
                         font=("Segoe UI", 11, "bold"), text_color=dev_col,
                         anchor="w").pack(side="left", padx=(4, 8))
            if mode == "vst" and self._vst_scan is not None:
                ptype = "vst2" if dev_name.startswith("VST2:") else "vst3"
                pname = dev_name[6:].strip()
                found = self._vst_scan.get((ptype, pname), False)
                ctk.CTkLabel(
                    row_f,
                    text="✓" if found else "✗",
                    font=("Segoe UI", 13, "bold"),
                    text_color="#4CAF50" if found else "#EF5350",
                    width=24,
                ).pack(side="right", padx=(4, 10))

    def _collect_all_vsts(self):
        vst2, vst3 = set(), set()
        sources = [self._data["main"]] + self._data["tracks"]
        for src in sources:
            vst2.update(src.get("vst2_plugins", []))
            vst3.update(src.get("vst3_plugins", []))
            for name in _rack_devices(src.get("rack_details", []), "vst"):
                if name.startswith("VST2: "):
                    vst2.add(name[6:])
                elif name.startswith("VST3: "):
                    vst3.add(name[6:])
        return sorted(vst2), sorted(vst3)

    def _run_vst_scan(self, btn, summary_lbl):
        btn.configure(state="disabled", text="Сканирование...")
        summary_lbl.configure(text="")
        vst2_names, vst3_names = self._collect_all_vsts()
        def _do():
            results = scan_vst_plugins(vst2_names, vst3_names)
            self.after(0, lambda: self._on_vst_scan_done(results))
        threading.Thread(target=_do, daemon=True).start()

    def _on_vst_scan_done(self, results):
        self._vst_scan = results
        tab = self._tabview.tab("VST")
        for w in tab.winfo_children():
            w.destroy()
        self._build_tab_list(tab, self._data, "vst")

    def _copy_report(self):
        if self._data is None:
            return
        self.clipboard_clear()
        self.clipboard_append(_build_report(self._data))
        messagebox.showinfo("Готово", "Отчёт скопирован в буфер обмена.")


if __name__ == "__main__":
    app = App()
    app.mainloop()
