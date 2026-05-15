import json
import os
import pandas as pd
from typing import Dict, Optional

MAPPING_FILE = "supplier_mappings.json"

FIELD_ALIASES = {
    "index": ["Index", "#", "Line Item", "Line"],
    "sku": [
        "DigiKey Part #",
        "Mouser #",
        "Supplier Part",
        "SKU",
        "Part Number",
        "Supplier Part Number",
    ],
    "mpn": [
        "Manufacturer Part Number",
        "Mfr. #",
        "MPN",
        "Mfr Part #",
        "Mfr Part Number",
    ],
    "quantity": ["Quantity", "Qty", "Amount", "Quantity Shipped", "Order Qty."],
    "unit_price": ["Unit Price", "Price", "Cost", "Price Each", "Price (USD)"],
    "description": ["Description", "Product Description", "Item Description"],
    "manufacturer": ["Manufacturer", "Mfr", "Make"],
    "customer_reference": [
        "Customer Reference",
        "Customer #",
        "Ref",
        "PO Number",
        "Customer Ref",
    ],
}

REQUIRED_FIELDS = ["sku", "mpn", "quantity", "unit_price", "description"]


def load_mappings() -> Dict:
    if os.path.exists(MAPPING_FILE):
        try:
            with open(MAPPING_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_mapping(supplier_id: str, mapping: Dict[str, str]):
    mappings = load_mappings()
    mappings[str(supplier_id)] = mapping
    with open(MAPPING_FILE, "w") as f:
        json.dump(mappings, f, indent=4)


def get_saved_mapping(supplier_id: str) -> Optional[Dict[str, str]]:
    mappings = load_mappings()
    return mappings.get(str(supplier_id))


def find_csv_header(filepath: str) -> int:
    """Finds the 0-based index of the header row in a CSV file."""
    try:
        # Read the first 20 lines to find the header
        with open(filepath, "r") as f:
            lines = [f.readline() for _ in range(20)]

        # Flatten all aliases into a single set for fast lookup
        all_aliases = {
            alias.lower() for aliases in FIELD_ALIASES.values() for alias in aliases
        }

        best_row = 0
        max_matches = -1

        for i, line in enumerate(lines):
            if not line.strip():
                continue

            # Simple heuristic: count how many aliases are in this row
            parts = [p.strip().lower() for p in line.split(",")]
            matches = sum(1 for p in parts if p in all_aliases)

            if matches > max_matches:
                max_matches = matches
                best_row = i

        return best_row
    except Exception:
        return 0


def detect_columns(filepath: str) -> Dict[str, Optional[str]]:
    """Try to auto-detect CSV columns based on common aliases."""
    header_row = find_csv_header(filepath)
    try:
        df = pd.read_csv(filepath, skiprows=header_row, nrows=0)
        headers = df.columns.tolist()
    except Exception:
        return {field: None for field in FIELD_ALIASES}

    mapping = {}
    for field, aliases in FIELD_ALIASES.items():
        match = None
        # Try exact match first
        for header in headers:
            if header.strip().lower() == field.lower():
                match = header
                break

        # Try aliases
        if not match:
            for alias in aliases:
                for header in headers:
                    if header.strip().lower() == alias.lower():
                        match = header
                        break
                if match:
                    break

        mapping[field] = match

    return mapping
