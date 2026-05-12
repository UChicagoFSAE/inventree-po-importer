# Project Agent Instructions: InvenTree PO Importer

This document provides context, architectural patterns, and project direction for AI coding agents maintaining or extending this repository.

## 1. Project Description & Feature Summary

**InvenTree PO Importer** is a Python-based CLI tool designed to bridge the gap between supplier invoice CSVs (e.g., DigiKey) and an [InvenTree](https://inventree.org/) inventory instance.

### Current Features:
- **Supplier Reconciliation:** Resolves CSV rows to InvenTree parts using a two-tier lookup:
    1. **SKU Match:** Direct match via `SupplierPart`.
    2. **MPN Fallback:** Match via `ManufacturerPart` to trace the base part.
- **Interactive Fallback:** If automated resolution fails, users can:
    - Search InvenTree for similar parts.
    - Manually link to a known Part ID or IPN.
    - Create a new Part, Manufacturer, and associated links on-the-fly.
- **Visual Verification (TUI):** Displays a color-coded comparison of CSV data vs. retrieved InvenTree metadata to ensure accuracy.
- **Direct Stock Creation:** Bypasses the Purchase Order state machine to directly create `StockItem` objects in a specified location with quantity and pricing data.
- **Detailed Audit Trail:** Provides a post-execution summary table with internal Primary Keys (PKs) for all created records.

## 2. Project Direction

The project follows an iterative roadmap toward full supply chain automation:
1. **Phase 1 (Complete):** Read-only reconciliation and metadata retrieval.
2. **Phase 2 (Current):** Direct Stock creation and interactive part resolution.
3. **Phase 3 (Next):** Implement full **Purchase Order (PO) lifecycle** management (Create PO -> Add Lines -> Issue PO -> Receive PO) to maintain formal accounting records.
4. **Phase 4:** Generic supplier mapping (Configurable CSV header maps for Mouser, LCSC, etc.).

## 3. Architecture & Coding Conventions

### Data Pipeline Architecture
To prevent tight coupling between the CSV format and the InvenTree API, the project uses a **Modular Pipeline** pattern:
- **`models.py`**: Central `LineItem` dataclass. Every stage of the pipeline must consume and/or enrich this object.
- **`parser.py`**: Responsible for CSV-to-Dataclass mapping.
- **`resolver.py`**: Handles lookups, search, and creation logic. Use `part_cache` to minimize redundant API calls.
- **`stock_manager.py`**: Handles state-mutating writes for stock items.

### Technical Stack
- **Python 3.10+**: Utilize type hinting and `dataclasses`.
- **`inventree`**: Official Python bindings.
- **`pandas`**: Used for robust CSV parsing and data cleaning.
- **`click`**: CLI framework.
- **`tabulate`**: Used for TUI table formatting.

### Conventions
- **Interactive Prompts:** Use `click.prompt` and `click.confirm` for manual resolution steps. Ensure default values from the CSV are provided to speed up the workflow.
- **Surgical Edits:** Maintain existing whitespace and formatting (4-space indentation).
- **Error Handling:** Log errors to the `LineItem` and display them in the final summary table. Do not abort the entire batch for a single row error.
- **API Efficiency:** Always prefer filtered `list()` or `search()` calls over iterating through all parts.

## 4. Important Metadata Mapping
When resolving or creating parts, ensure the following fields are captured:
- `IPN`: Internal Part Number.
- `SKU`: Supplier Stock Keeping Unit (stored in `SupplierPart`).
- `MPN`: Manufacturer Part Number (stored in `ManufacturerPart`).
- `Manufacturer`: The company identified as the manufacturer.

## 5. Development Workflow for Agents
1. **Research:** Check `models.py` when adding new data fields and `resolver.py` for API interaction patterns.
2. **Strategy:** Maintain the separation between *Resolution* (lookup/link) and *Action* (writing stock changes).
3. **Verification:** Verify against the provided sample CSV in `./examples/` or specified in the prompt.
