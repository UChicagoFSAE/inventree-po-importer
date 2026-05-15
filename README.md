# InvenTree PO Importer

A command-line tool to bridge the gap between supplier invoice CSVs (like DigiKey) and your [InvenTree](https://inventree.org/) inventory. It automates the process of reconciling parts and creating stock items, and provides a powerful workflow for aggregating student project carts.

## Features

- **Generic CSV Mapping**: Automatically detects columns for various suppliers and allows manual mapping adjustment with persistent configuration.
- **Automated Reconciliation**: Matches parts using Supplier SKU and Manufacturer Part Number (MPN).
- **Interactive Resolution**: If a part isn't found, you can search InvenTree, manually link a known ID, or create a new part on-the-fly.
- **Classroom Procurement Workflow**: Aggregate multiple student Mouser carts, allocate existing stock, and automatically generate Purchase Orders (POs) for shortages.
- **API-Driven Parameter Matching**: Strategic hooks for Octopart/Nexar integration to automatically resolve parts via technical parameters (e.g., Capacitance, Package).
- **Direct Stock Import**: Creates stock items directly in a specified location with correct pricing and quantities.

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/youruser/inventree-po-importer.git
   cd inventree-po-importer
   ```

2. Create a virtual environment and install dependencies:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. Configure your environment:
   Copy `.env.example` to `.env` and fill in your InvenTree API credentials:
   ```bash
   INVENTREE_API_URL=https://your-inventree-server.com/api/
   INVENTREE_API_TOKEN=your_secret_token
   # Optional: Add external API keys for parameter matching
   # OCTOPART_API_KEY=your_key
   ```

## Usage

The tool uses a multi-command CLI structure. Use `--help` to see all options.

### 1. Direct Invoice Import
Reconcile a supplier CSV (invoice) and import stock items directly into a location.

```bash
python3 cli.py import-invoice ./examples/invoice.csv --supplier-id 5 --location-id 10
```

### 2. Classroom Procurement (Cart Aggregation)
Aggregate multiple student cart CSVs, calculate stock allocations, and generate a PO for shortfalls.

```bash
python3 cli.py process-carts ./student_carts/*.csv --supplier-id 12 --output allocations.csv
```

*Note: Student identification is strictly handled via the CSV filename (e.g., `Alice Smith.csv` -> "Alice Smith").*

## Advanced Workflows

### Classroom Allocation Logic
When running `process-carts`, the system:
1.  **Aggregates** all items across all provided CSV files.
2.  **Resolves** items to InvenTree **Base Parts** (the generic parts in your inventory).
3.  **Allocates** available local stock to students on a first-come, first-served basis (by file order).
4.  **Generates** a local `allocations.csv` pick-list for staff.
5.  **Creates** a native Draft Purchase Order in InvenTree for all shortages, automatically selecting your **Preferred Supplier Part** for each generic base part.

## Supported Suppliers

The tool supports **generic CSV mapping**, meaning it can work with any supplier (DigiKey, Mouser, LCSC, etc.) by mapping their specific column headers to the internal `LineItem` format. 

Mappings are saved to `supplier_mappings.json` and reused automatically based on the `--supplier-id` you provide.
