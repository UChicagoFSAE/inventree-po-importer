import json
import os
import pandas as pd
from typing import Dict, Optional

MAPPING_FILE = "supplier_mappings.json"

FIELD_ALIASES = {
    "index": ["Index", "#", "Line Item", "Line"],
    "sku": [
        "DigiKey Part #",
        "Supplier Part",
        "SKU",
        "Part Number",
        "Supplier Part Number",
    ],
    "mpn": ["Manufacturer Part Number", "MPN", "Mfr Part #", "Mfr Part Number"],
    "quantity": ["Quantity", "Qty", "Amount", "Quantity Shipped"],
    "unit_price": ["Unit Price", "Price", "Cost", "Price Each"],
    "description": ["Description", "Product Description", "Item Description"],
    "manufacturer": ["Manufacturer", "Mfr", "Make"],
    "customer_reference": ["Customer Reference", "Ref", "PO Number", "Customer Ref"],
}

REQUIRED_FIELDS = ["index", "sku", "mpn", "quantity", "unit_price", "description"]


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


def detect_columns(filepath: str) -> Dict[str, Optional[str]]:
    """Try to auto-detect CSV columns based on common aliases."""
    try:
        df = pd.read_csv(filepath, nrows=0)
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
