# Project Agent Instructions: InvenTree PO Importer

This document provides context, architectural patterns, and project direction for AI coding agents maintaining or extending this repository.

## 1. Project Description & Feature Summary

**InvenTree PO Importer** is a Python-based CLI tool designed to bridge the gap between supplier invoice CSVs (e.g., DigiKey) and an [InvenTree](https://inventree.org/) inventory instance.

### Current Features:
- **Supplier Reconciliation:** Resolves CSV rows to InvenTree parts using a three-tier lookup:
    1. **SKU Match:** Direct match via `SupplierPart`.
    2. **MPN Fallback:** Match via `ManufacturerPart` to trace the base part.
    3. **Parameter Match:** Queries Mouser/DigiKey APIs for technical attributes and searches InvenTree for matching Base Parts (Fast-track for passives).
- **Classroom Procurement Aggregator:** Process multiple student carts, calculate local stock allocations, and generate native InvenTree Purchase Orders (POs) for shortages.
- **Interactive Fallback (TUI):** If automated resolution fails, users can search InvenTree or create new parts. API data is used to **pre-fill** creation forms (Name, Description, Mfr).
- **Visual Verification (TUI):** Displays a color-coded comparison of CSV data vs. retrieved InvenTree metadata to ensure accuracy.
- **Direct Stock Creation:** Handles direct `StockItem` creation for validated invoices.
- **Detailed Audit Trail:** Provides post-execution summary tables and CSV allocation reports.

## 2. Project Direction

The project follows an iterative roadmap toward full supply chain automation:
1. **Phase 1 (Complete):** Read-only reconciliation and metadata retrieval.
2. **Phase 2 (In-Progress):** Direct Stock creation, interactive part resolution, and Procurement Aggregation.
3. **Phase 3 (Next):** Implement full **Purchase Order (PO) lifecycle** management (Create PO -> Add Lines -> Issue PO -> Receive PO) to maintain formal accounting records.
4. **Phase 4:** Generic supplier mapping (Configurable CSV header maps for Mouser, LCSC, etc.).

## 3. Architecture & Coding Conventions

### Data Pipeline Architecture
To prevent tight coupling between the CSV format and the InvenTree API, the project uses a **Modular Pipeline** pattern:
- **`models.py`**: Central `LineItem` dataclass. Every stage of the pipeline must consume and/or enrich this object.
- **`parser.py`**: Responsible for CSV-to-Dataclass mapping. Handles student name extraction from filenames.
- **`resolver.py`**: Handles lookups, search, and parameter-based resolution logic.
- **`stock_manager.py`**: Handles state-mutating writes for stock items.
- **`procurement_manager.py`**: New module for aggregating student carts, calculating allocations, and generating native POs.

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
4. **Linting and Formatting** We utilize Ruff as the linter and formatter. Please run Ruff when you make changes.
