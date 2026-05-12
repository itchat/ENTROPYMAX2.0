# ENTROPYMAX 2.0

> ### Project Origin and Maintenance
>
> This repository is a maintained continuation of **ENTROPYMAX 2.0**, originally developed as a **University of Western Australia CITS3200 capstone group project (Group 31)** for the **UWA Oceans Institute**.
>
> The original group implementation produced the working first release. This fork is maintained by [@itchat](https://github.com/itchat) post-graduation for continued development, bug fixes, performance improvements, and ongoing feature work.
>
> **Original group repository:** [github.com/CITS3200-group-31/ENTROPYMAX2.0](https://github.com/CITS3200-group-31/ENTROPYMAX2.0)

---

*A modernised version of the EntropyMax application for geological and geophysical analysis and data processing, with built‑in interactive visualisation that reduces or eliminates the need to move results into spreadsheets or other external software for plotting and mapping.*

---

## Table of Contents

* [Project Overview](#project-overview)
* [Roadmap](#roadmap)
* [Project Structure](#project-structure)
* [Development Status](#development-status)
* [Contributing](#contributing)
* [License](#license)
* [Contact](#contact)

## Project Overview

**ENTROPYMAX 2.0** is a ground‑up rewrite of the original EntropyMax that preserves its legacy geological and geophysical analysis core while **enhancing with a rigorously maintainable and extensible architecture**. Embedded, interactive visualisation is an intended requirement—every analytical routine should render maps, charts and cross‑plots directly inside the application, reducing or eliminating the time spent exporting data to spreadsheets or other external tools for refining, plotting, and mapping. **By design, the system aims to transfer as much cognitive load as possible from the user to the computer—automating repetitive analysis so geoscientists can concentrate on high‑value interpretation.** **Operating under a tight semester timeline, we are doubling‑down on clean‑code conventions, modular interfaces and comprehensive automated tests to ensure that future developers can add features or refine algorithms swiftly and safely—without wrestling with technical debt or fresh legacy complexity.**

## Roadmap

Project work is organised into three sprints aligned with UWA Semester 2 2025.

| Sprint | Date window | Focus                                                            | Intended outcomes                                                                                                                                                            |
| ------ | ----------- | ---------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1**  | Jul → Aug   | Legacy audit, architecture planning & visualisation requirements | · Select technology stack (including plotting/visualisation libraries)· Define module boundaries and data‑flow for on‑screen plots· Complete migration repository and documentation. Establish roles and CI/CD.     |
| **2**  | Aug → Sep   | Core algorithms **& visualisation prototype**                    | · Port first analytical module· Prototype in‑app plotting pipeline (e.g., interactive maps, scatter/line charts)· Establish automated test harness· Draft public API         |
| **3**  | Sep → Oct   | **User experience & advanced visualisation**                     | · Deliver fully integrated visualisation dashboard with export‑free workflow· Add sample datasets and tutorials showcasing plotting features· Finalise developer & user docs |

## Project Structure

```
ENTROPYMAX2/
├── README.md
├── .gitignore
├── pyproject.toml                   # Python deps & build (PyQt6, numpy, cffi, etc.)
├── scripts/
│  ├── build_backend.sh              # cmake -S backend -B backend/build && cmake --build backend/build
│  └── dev_run.sh                    # python -m app
├── backend/                         # Modular C backend
│  ├── CMakeLists.txt
│  ├── include/                      # headers: backend.h, preprocess.h, metrics.h, grouping.h, sweep.h, csv.h, parquet.h, util.h
│  ├── src/
│  │  ├── algo/                      # core algorithm implementation (glue + modules)
│  │  ├── io/                        # merge gps.csv + raw.csv → raw Parquet; write processed Parquet
│  │  ├── util/                      # helpers
│  │  └── cli/                       # emx_cli: raw.parquet -> processed.parquet
│  └── tests/
│     └── test_backend.c
├── src/                             # Python package (src layout)
│  └── app/
│     ├── __init__.py
│     ├── __main__.py                # entrypoint: `python -m app`
│     ├── config.py
│     ├── core/
│     │  ├── datastore.py            # NumPy/Arrow table access
│     │  └── io.py                   # CSV/Parquet loaders
│     ├── bindings/
│     │  ├── __init__.py
│     │  ├── _lib.py                 # locate & dlopen lib across OSes
│     │  ├── cffi_backend.py         # cffi wrapper (start here)
│     │  └── cython_backend/
│     │     ├── __init__.py
│     │     └── wrapper_cy.pyx
│     ├── gui/
│     │  ├── main_window.py          # QMainWindow, menus, actions
│     │  ├── worker.py               # QThread worker calling backend
│     │  ├── plot_view.py            # PyQtGraph plotting widget(s)
│     │  ├── map_view.py             # QWebEngineView bridge
│     │  └── assets/
│     │     ├── map.html             # minimal Leaflet page
│     │     └── qrc/                 # icons, qss, etc.
│     └── lib/                       # (optional) ship native libs with wheel/app
├── tests/
│  ├── python/
│  │  ├── test_cffi_wrapper.py
│  │  ├── test_datastore.py
│  │  └── test_gui_smoke.py
│  └── data/
│     ├── sample_raw.csv
│     └── sample_processed.parquet
├── data/
│  ├── raw/
│  └── processed/
└── legacy/                           # Original VB6 sources (read‑only)
```

## Quick start (dev)

### 1) Backend (C)
Requirements: CMake ≥ 3.16; a C11 compiler (clang/gcc).

```bash
chmod +x scripts/build_backend.sh
./scripts/build_backend.sh
```

Outputs:
- Static library: `backend/build/libentropymax.*`
- CLI executable: `backend/build/emx_cli`

### 2) Frontend (PyQt6)
You can run either the standalone frontend app, or the prototype under `src/app`.

Standalone frontend (recommended):
```bash
cd frontend
python3 -m venv .venv && source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python main.py
```

Prototype entry (src/app):
```bash
python -m app
```

Notes
- Python GUI dependencies for the standalone frontend are declared in `frontend/requirements.txt`.
- The C backend CSV/Parquet I/O is currently a placeholder; the CLI may return non‑zero until implemented.

## Development Status

- C backend builds and links; CSV/Parquet I/O are placeholders pending implementation.
- PyQt6 frontend runs with sample data and smoke tests.

## Tests

### C tests (CTest)
```bash
cd backend/build
ctest --output-on-failure
```

### Python tests (pytest)
```bash
python -m pip install -r frontend/requirements.txt  # provides GUI deps
python -m pip install -r requirements-dev.txt       # dev/test tools (pytest, coverage, ruff, mypy)
pytest -q tests/python
```

## Further reading
- `docs/README.md` — documentation index.
- `docs/ARCHITECTURE.md` — working architecture document.
- `docs/PORTING_GUIDE.md` — mapping VB6 routines to C modules and owners.
- `docs/BACKEND.md` — backend C library and CLI details.
- `docs/SAMPLE_API_FORMAT.md` — sample API/document format.
- `docs/drafts/` — archived drafts (historical);
  - `docs/drafts/DRAFT_architecture.md` — superseded by `docs/ARCHITECTURE.md`.
  - `docs/drafts/DRAFT_ci_cd.md` — proposed CI/CD pipeline (not yet implemented).
  - `docs/drafts/README2.md` — superseded detailed architecture.

## Contributing

We welcome feedback, bug reports and feature ideas via **GitHub Issues** or **Discussions** from interested external parties. Please note that **pull requests will not be considered** until the assessed component of UWA’s CITS3200 unit concludes (late October 2025) to preserve academic integrity *and our sanity*.

## License

MIT (provisional) — subject to final approval.

## Contact

[CITS3200 Group 31](https://github.com/CITS3200-group-31/ENTROPYMAX2.0)
