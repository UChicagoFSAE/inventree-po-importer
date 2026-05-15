import pandas as pd
import os
from typing import List
from models import LineItem
from mapping_utils import find_csv_header


def parse_csv(filepath: str, mapping: dict) -> List[LineItem]:
    header_row = find_csv_header(filepath)
    # Read CSV skipping leading junk
    df = pd.read_csv(filepath, skiprows=header_row)

    # Determine default student name from filename
    filename = os.path.basename(filepath)
    default_student_name = os.path.splitext(filename)[0]

    # Filter to only rows that have the core data
    # Use mapped columns for sku and mpn if available for filtering
    subset = [mapping[f] for f in ["sku", "mpn"] if mapping.get(f)]
    if subset:
        df = df.dropna(subset=subset)

    line_items = []
    for i, row in df.iterrows():
        try:
            # Helper to get value from mapped column
            def get_val(field):
                col = mapping.get(field)
                if col and col in row and pd.notna(row[col]):
                    return row[col]
                return None

            unit_price_raw = str(get_val("unit_price") or "0")
            # Remove common currency symbols and thousands separators
            unit_price_clean = (
                unit_price_raw.replace("$", "")
                .replace("£", "")
                .replace("€", "")
                .replace(",", "")
                .strip()
            )

            customer_ref = (
                str(get_val("customer_reference")).strip()
                if get_val("customer_reference")
                else None
            )

            # Use dataframe index if 'index' field is not mapped
            idx_val = get_val("index")
            if idx_val is None:
                idx_val = i + 1

            item = LineItem(
                index=int(idx_val),
                sku=str(get_val("sku")).strip(),
                mpn=str(get_val("mpn")).strip(),
                manufacturer=str(get_val("manufacturer")).strip()
                if get_val("manufacturer")
                else None,
                quantity=float(get_val("quantity")),
                unit_price=float(unit_price_clean),
                description=get_val("description"),
                customer_reference=customer_ref,
                student_name=default_student_name,
            )
            line_items.append(item)
        except (ValueError, TypeError) as e:
            idx_col = mapping.get("index")
            idx_val = row.get(idx_col) if idx_col else i + 1
            print(f"Warning: Skipping row {idx_val} due to parsing error: {e}")

    return line_items


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        items = parse_csv(sys.argv[1])
        print(f"Parsed {len(items)} items.")
        for item in items[:3]:
            print(item)
