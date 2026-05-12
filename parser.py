import pandas as pd
from typing import List
from models import LineItem


def parse_csv(filepath: str, mapping: dict) -> List[LineItem]:
    # Read CSV
    df = pd.read_csv(filepath)

    # Filter to only rows that have the core data (ignore Subtotal row)
    # Use mapped columns for index, sku, and mpn if available for filtering
    subset = [mapping[f] for f in ["index", "sku", "mpn"] if mapping.get(f)]
    if subset:
        df = df.dropna(subset=subset)

    line_items = []
    for _, row in df.iterrows():
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

            item = LineItem(
                index=int(get_val("index")),
                sku=str(get_val("sku")).strip(),
                mpn=str(get_val("mpn")).strip(),
                manufacturer=str(get_val("manufacturer")).strip()
                if get_val("manufacturer")
                else None,
                quantity=float(get_val("quantity")),
                unit_price=float(unit_price_clean),
                description=str(get_val("description")).strip(),
                customer_reference=str(get_val("customer_reference")).strip()
                if get_val("customer_reference")
                else None,
            )
            line_items.append(item)
        except (ValueError, TypeError) as e:
            idx_col = mapping.get("index")
            idx_val = row.get(idx_col) if idx_col else "unknown"
            print(f"Warning: Skipping row {idx_val} due to parsing error: {e}")

    return line_items


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        items = parse_csv(sys.argv[1])
        print(f"Parsed {len(items)} items.")
        for item in items[:3]:
            print(item)
