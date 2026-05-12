# Project Agent Instructions: InvenTree PO Importer

This document provides context, architectural patterns, and project direction for AI coding agents maintaining or extending this repository.

## 1. Project Description & Feature Summary

**InvenTree PO Importer** is a Python-based CLI tool designed to bridge the gap between supplier invoice CSVs (e.g., DigiKey) and an [InvenTree](https://inventree.org/) inventory instance.

### Current Features:
- **Supplier Reconciliation:** Resolves CSV rows to InvenTree parts using a two-tier lookup:
    1. **SKU Match:** Direct match via `SupplierPart`.
    2. **MPN Fallback:** Match via `ManufacturerPart` to trace the base part.
- **Visual Verification (TUI):** Displays a side-by-side comparison of CSV data vs. retrieved InvenTree metadata (Part Name, IPN, Description) to ensure mapping accuracy.
- **Direct Stock Creation:** Bypasses the Purchase Order state machine to directly create `StockItem` objects in a specified location with quantity and pricing data.
- **Detailed Audit Trail:** Provides a post-execution summary table with internal Primary Keys (PKs) for all created records.

## 2. Project Direction

The project follows an iterative roadmap toward full supply chain automation:
1. **Phase 1 (Complete):** Read-only reconciliation and metadata retrieval.
2. **Phase 2 (Current):** Direct Stock creation for rapid intake.
3. **Phase 3 (Next):** Implement full **Purchase Order (PO) lifecycle** management (Create PO -> Add Lines -> Issue PO -> Receive PO) to maintain formal accounting records.
4. **Phase 4:** Generic supplier mapping (Configurable CSV header maps for Mouser, LCSC, etc.).

## 3. Architecture & Coding Conventions

### Data Pipeline Architecture
To prevent tight coupling between the CSV format and the InvenTree API, the project uses a **Modular Pipeline** pattern:
- **`models.py`**: Central `LineItem` dataclass. Every stage of the pipeline must consume and/or enrich this object. Do not pass raw dictionaries between modules.
- **`parser.py`**: Responsible for CSV-to-Dataclass mapping.
- **`resolver.py`**: Responsible for InvenTree lookups and metadata enrichment. Use `part_cache` to minimize redundant API calls.
- **`stock_manager.py`**: Handles state-mutating writes.

### Technical Stack
- **Python 3.10+**: Utilize type hinting and `dataclasses`.
- **`inventree`**: Official Python bindings. Avoid raw REST calls unless the library lacks a specific action.
- **`pandas`**: Used for robust CSV parsing and data cleaning.
- **`click`**: CLI framework. Ensure all mutating actions have a `click.confirm()` guard.
- **`tabulate`**: Used for TUI table formatting.

### Conventions
- **Surgical Edits:** When using `replace`, ensure you maintain the existing whitespace and formatting (4-space indentation).
- **Error Handling:** Never let the tool crash on a single bad CSV row. Log the error to the `LineItem` and display it in the final summary table.
- **API Efficiency:** InvenTree instances can be slow. Always prefer filtered `list()` calls over iterating through all parts.

## 4. Important Metadata Mapping
When resolving parts, ensure the following fields are captured:
- `IPN`: Internal Part Number (stored in InvenTree Part `IPN` field).
- `SKU`: Supplier Stock Keeping Unit (stored in `SupplierPart`).
- `MPN`: Manufacturer Part Number (stored in `ManufacturerPart`).

## 5. Development Workflow for Agents
1. **Research:** Always check `models.py` first when adding new data fields.
2. **Strategy:** Propose changes that maintain the separation between *Resolution* (looking up what it is) and *Action* (writing what to do with it).
3. **Verification:** Always verify against the provided sample CSV in `./examples/` or specified in the prompt.
