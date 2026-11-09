# Export Information (QGIS Plugin)

A QGIS 3 plugin that exports HUB BOX, SUB BOX, Distribution Cable and pole information to a formatted Excel workbook.

## Main rules

- Reads `HUB BOX`, `SUB BOX`, and `Distribution Cable` vector layers.
- Reads pole layers under the `Poles` layer-tree group, including `New Pole` and `Exsiting Pole` (the common spelling `Existing Pole` is also accepted). The dialog allows manual selection if names differ.
- Parses SUB BOX names like `KIM-HB09L4S4` into HUB ID `KIM-HB09`, link `L4`, and sequence `S4`.
- Sorts records by HUB number, then L number, then S number using numeric ordering.
- Matches HUB BOX and SUB BOX independently to the nearest selected pole within the configured radius (3 m by default). Output coordinates are taken from the matched pole and formatted as `latitude, longitude` in EPSG:4326.
- Keeps unmatched BOX records; the pole name and coordinate are blank and the issue is listed in `QA Report`.
- Exports `DIST. Cable Core = 1` and `Subbox Port = 1`.
- Creates `ODN TRACE` and `QA Report` worksheets. No source QGIS layer is edited.

## Distribution Cable matching

The exporter first looks for the full HUB/L key (for example `KIM-HB09L4`) in cable attributes, then tries a link/port attribute equal to `L4`. If neither exists, it selects the geometrically nearest Distribution Cable feature to the SUB BOX. Geometry-based fallback and distant matches are explicitly flagged in `QA Report` for review. The selected feature's configured `Span` value is exported.

## Install

1. Download the plugin ZIP from the repository's **Actions** artifact after the build workflow runs.
2. In QGIS: **Plugins → Manage and Install Plugins → Install from ZIP**.
3. Select the ZIP and enable **Export Information**.
4. Open the plugin from the toolbar or **Plugins → Export Information**.

## Requirements

- QGIS 3.22 or later.
- No third-party Python package is required for Excel writing; XLSX is generated using Python's standard library.
