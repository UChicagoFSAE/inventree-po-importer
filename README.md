# InvenTree PO Importer

A command-line tool to bridge the gap between supplier invoice CSVs (like DigiKey) and your [InvenTree](https://inventree.org/) inventory. It automates the process of reconciling parts and creating stock items, with an interactive fallback for items that don't immediately match your database.

## Features

- **Automated Reconciliation**: Matches parts using Supplier SKU and Manufacturer Part Number (MPN).
- **Interactive Resolution**: If a part isn't found, you can search InvenTree, manually link a known ID, or create a new part on-the-fly.
- **On-the-fly Creation**: Create missing Parts, Manufacturers, and their associated links (ManufacturerParts/SupplierParts) without leaving the CLI.
- **Visual Verification**: Displays color-coded tables showing exactly how CSV data maps to your InvenTree metadata.
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
   ```

## Usage

Run the importer by providing the path to your supplier CSV, the destination stock location ID, and the supplier ID:

```bash
python3 cli.py --location-id 10 --supplier-id 5 ./examples/invoice.csv
```

### Workflow

1. **Resolution**: The tool first attempts to match every item in the CSV automatically.
2. **Review & Fallback**: A table is displayed showing the results. If items are missing, you'll be prompted to resolve them manually.
3. **Interactive Menu**: For each unresolved item, you can:
   - Select from suggested search results.
   - Search again with custom terms.
   - Enter a Part PK or IPN manually.
   - Create a new Part (with optional Manufacturer creation).
4. **Verification**: After resolution, a final table shows the status of all items.
5. **Import**: Confirm the stock creation to finalize the process.

## Supported Suppliers

Currently, the tool is tuned for **DigiKey** invoice CSVs. Support for Mouser, LCSC, and others is planned.
