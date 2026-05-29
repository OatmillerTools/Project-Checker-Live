# Ableton Project Checker

![ProjectChecker](ProjectChecker.gif)

A desktop tool for analyzing Ableton Live projects (`.als`). Drag a project file into the window and get a full picture: tracks, plugins, automation, sample availability, and master channel status.

![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS-blue)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

---

## Compatibility

| | Version |
|---|---|
| Ableton Live | 10, 11, 12 (tested on 12.4) |
| Windows | 10, 11 (tested on 11) |
| macOS | 12 Monterey and later (tested on 14 Sonoma) |

The parser reads XML directly from the `.als` gzip archive and should work with any version of Live that uses the same format.

---

## Features

- **Tracks** — all MIDI, Audio, Group, and Return tracks with fader levels, mute status, and group nesting
- **Plugins** — full list of VST2 and VST3 plugins across the entire project, including rack contents
- **Live devices** — instruments, audio effects, and MIDI effects (native and Max for Live)
- **Racks** — expandable view of Instrument Rack, Audio Effect Rack, Drum Rack, and MIDI Effect Rack with each chain's contents
- **Sends** — send levels to return buses for each track
- **Automation** — marks tracks that contain automation
- **Samples** — checks whether audio files are collected into the project folder or missing (useful for verifying "Collect All and Save")
- **Arrangement length** — total length in bars and minutes at the project's current BPM
- **Master channel** — fader level and full device list on the master
- **Copy report** — one-click text report to clipboard
- **Plugin scan** — checks whether VST2/VST3 plugins used in the project are present in system folders (VST tab → "Scan plugins")
- **Language switch** — toggle between Russian and English interface (RU / EN buttons in the header)

---

## Installation

No installation required. Download the binary for your platform and run it directly.

| Platform | File | Note |
|---|---|---|
| Windows | `AbletonProjectChecker.exe` | Portable — just run the `.exe` |
| macOS | `AbletonProjectChecker.app` | Portable — run directly or drag to Applications |

---

## Usage

1. Launch the app
2. Drag an `.als` file into the window or click **Open .als file**
3. Switch between tabs:
   - **Tracks** — detailed info for each track with content
   - **Instruments** — flat list of all instruments on tracks with content
   - **Audio FX** — flat list of all audio effects on tracks with content
   - **MIDI FX** — flat list of MIDI effects on tracks with content
   - **VST** — all third-party plugins in one place, with an option to check their presence on your system
4. Click **Copy report** to copy a text summary to the clipboard
