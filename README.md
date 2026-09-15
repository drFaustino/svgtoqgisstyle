# SVG to QGIS Style

Plugin for **QGIS 4.x (Qt6)** that converts one or more SVG files (including entire folder trees) into a single QGIS style file (.xml). 
This file can then be imported into the **QGIS Style Manager**. 
The plugin allows you to apply custom background and fill colors and preview the results before conversion.

## Requirements

- QGIS 4.x with Qt6 (PyQt6 / PyQtSvg).

## Installation

1. Copy the entire `svgtoqgisstyle` folder into the QGIS plugins directory, typically located at:
   - Windows: `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\`
   - Linux/macOS: `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`
     (The path name may differ slightly depending on the version; look for the python/plugins folder of the active QGIS profile).
2. Start QGIS and activate the plugin via
   **Plugins → Manage and Install Plugins → Installed**.
3. An icon will be added to the toolbar, and a corresponding entry will appear in the **Plugins** menu.

Alternatively, you can install the plugin from a `.zip` archive via **Plugins → Manage and Install Plugins → Install from ZIP**.

## Usage

1. **Select folder or SVG files…**: 
   Allows you to choose a single folder (SVG files are also searched within subfolders) or one or more individual SVG files. 
   The icons are loaded into a list showing a 64×64 preview.
2. **Preview Colors**:
   - *Apply background color / Apply fill color*: 
     Enable the replacement of, respectively, the first fill color encountered in the SVG file (typically the background shape) 
     and all subsequent fill colors (typically the foreground symbol). Clicking on the colored box opens the color picker.
   - *Apply to*: 
     Choose whether to apply colors to **all** icons in the list or only to the **selected** ones.
   - *Apply preview*: Recolors the chosen icons (in preview only, without modifying the original files on disk).
   - *Reset original colors*: Prompts for confirmation and restores all modified icons to their original colors.
3. **FQGIS Style File → Select destination…**: Choose where to save the resulting .xml style file.
4. **Start conversion**: Generates a single QGIS style file containing a marker symbol *marker* (`SvgMarker`) for each loaded SVG file. 
   Progress is shown in the progress bar.
   - If preview colors have been applied to one or more icons, the plugin writes **recolored copies** of the corresponding SVG files into 
     a subfolder named `<nome_stile>_svg/` right next to the style file, and points the symbol to that copy (original SVG files are never modified).
   - Unmodified icons are referenced directly using their original paths.
5. Import the generated `.xml` le into QGIS via **Settings → Style Manager… → Import/Export → Import Items**.

## Technical Notes

- **Recoloring Heuristic**: The "background / fill" association is based on the order of appearance of `fill` values (either the `fill="…"` attribute or the `fill:` property inside `style="…"`) in the SVG markup.The first color encountered is treated as the background, while all subsequent ones are treated as the fill. This works well with most two-color icons; SVGs with more than two distinct colors will only be partially recolored according to this logic (all colors from the second onwards will become the chosen fill color).
- The generated style file complies with the `<qgis_style version="2">` format used by QGIS for importing symbols into the Style Manager.
- The plugin is translation-ready. Interface strings are in English (source language), and translation files are located in `i18n/` (`svgtoqgisstyle_en.ts`, `svgtoqgisstyle_it.ts`), already compiled into their corresponding `.qm` files (automatically loaded by QGIS based on the interface language). To add a new language: create a new `svgtoqgisstyle_<codice_lingua>.ts` (e.g. `svgtoqgisstyle_fr.ts`), translate the messages using Qt Linguist, and compile it into `.qm` using `lrelease`/`pyside6-lrelease`. If new `self.tr(...)` strings are added to the code in the future, regenerate the `.ts` files using `pylupdate6`/`pyside6-lupdate` before recompiling them.

## Plugin Structure

```
svgtoqgisstyle/
├── __init__.py                  QGIS entry point (classFactory)
├── metadata.txt                 Plugin metadata
├── icon.png                     Toolbar/menu icon
├── svgtoqgisstyle.py            Main class (menu, toolbar, i18n)
├── svgtoqgisstyle_dialog.py     Dialog window and UI logic
├── svg_utils.py                 Pure functions: rendering, recoloring, XML
├── README.md
└── i18n/
    ├── svgtoqgisstyle_en.ts
    └── svgtoqgisstyle_it.ts
```
