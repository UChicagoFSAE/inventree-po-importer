from typing import List
from models import LineItem
from inventree.stock import StockItem


class StockManager:
    def __init__(self, api):
        self.api = api

    def create_stock(self, items: List[LineItem], location_id: int):
        """Creates StockItem objects for all resolved items and returns detailed results."""
        results = []

        for item in items:
            if not item.base_part_pk:
                continue

            result = {
                "sku": item.sku,
                "mpn": item.mpn,
                "ipn": item.internal_part_number,
                "name": item.part_name,
                "desc": item.part_description,
                "qty": item.quantity,
                "status": "Failed",
                "pk": None,
                "error": None,
            }

            try:
                data = {
                    "part": item.base_part_pk,
                    "location": location_id,
                    "quantity": item.quantity,
                    "purchase_price": item.unit_price,
                    "supplier_part": item.supplier_part_pk
                    if item.supplier_part_pk
                    else None,
                }

                # Create the stock item
                si = StockItem.create(self.api, data=data)

                # Handle cases where the API returns a list of objects
                if isinstance(si, list) and len(si) > 0:
                    si = si[0]

                result["pk"] = getattr(si, "pk", None)
                result["status"] = "Success"

            except Exception as e:
                result["status"] = "Failed"
                result["error"] = str(e)

            results.append(result)

        return results
