import pandas as pd
from typing import List
from models import LineItem


def parse_csv(filepath: str) -> List[LineItem]:
    # Read CSV
    # DigiKey CSVs often have extra rows at the end (like subtotal)
    df = pd.read_csv(filepath)

    # Define mapping (can be expanded later for other suppliers)
    mapping = {  # noqa: F841
        "Index": "index",
        "DigiKey Part #": "sku",
        "Manufacturer Part Number": "mpn",
        "Manufacturer": "manufacturer",
        "Quantity": "quantity",
        "Unit Price": "unit_price",
        "Description": "description",
        "Customer Reference": "customer_reference",
    }

    # Filter to only rows that have the core data (ignore Subtotal row)
    # The subtotal row usually has NaN for 'Index' or 'DigiKey Part #'
    df = df.dropna(subset=["Index", "DigiKey Part #", "Manufacturer Part Number"])

    line_items = []
    for _, row in df.iterrows():
        try:
            item = LineItem(
                index=int(row["Index"]),
                sku=str(row["DigiKey Part #"]).strip(),
                mpn=str(row["Manufacturer Part Number"]).strip(),
                manufacturer=str(row["Manufacturer"]).strip()
                if "Manufacturer" in row and pd.notna(row["Manufacturer"])
                else None,
                quantity=float(row["Quantity"]),
                unit_price=float(str(row["Unit Price"]).replace("$", "").strip()),
                description=str(row["Description"]).strip(),
                customer_reference=str(row["Customer Reference"]).strip()
                if pd.notna(row["Customer Reference"])
                else None,
            )
            line_items.append(item)
        except (ValueError, TypeError) as e:
            print(f"Warning: Skipping row {row.get('Index')} due to parsing error: {e}")

    return line_items


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        items = parse_csv(sys.argv[1])
        print(f"Parsed {len(items)} items.")
        for item in items[:3]:
            print(item)
