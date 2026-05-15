import csv
from typing import List, Dict, Optional
from models import LineItem
from inventree.part import Part
from inventree.company import SupplierPart
from inventree.purchase_order import PurchaseOrder, PurchaseOrderLineItem


class ProcurementManager:
    def __init__(self, api):
        self.api = api

    def aggregate_by_part(self, items: List[LineItem]) -> Dict[int, List[LineItem]]:
        """Groups LineItems by their resolved base_part_pk."""
        aggregated = {}
        for item in items:
            if item.base_part_pk:
                if item.base_part_pk not in aggregated:
                    aggregated[item.base_part_pk] = []
                aggregated[item.base_part_pk].append(item)
        return aggregated

    def get_stock_levels(self, part_pks: List[int]) -> Dict[int, float]:
        """Queries InvenTree for current stock levels of given part PKs."""
        stock_levels = {}
        for pk in part_pks:
            part = Part(self.api, pk=pk)
            # 'in_stock' is often a property/field on the Part object in the Python bindings
            stock_levels[pk] = float(getattr(part, "in_stock", 0))
        return stock_levels

    def generate_report(self, items: List[LineItem], filepath: str = "allocations.csv"):
        """Generates a CSV report detailing stock allocations and shortfalls for students."""
        aggregated = self.aggregate_by_part(items)
        stock_levels = self.get_stock_levels(list(aggregated.keys()))

        # Track remaining stock as we simulate allocation
        remaining_stock = stock_levels.copy()

        report_data = []
        shortfalls_by_pk = {}

        for part_pk, part_items in aggregated.items():
            shortfalls_by_pk[part_pk] = 0
            for item in part_items:
                requested = item.quantity
                available = remaining_stock[part_pk]

                allocated = min(requested, available)
                shortfall = max(0, requested - available)

                remaining_stock[part_pk] -= allocated
                shortfalls_by_pk[part_pk] += shortfall

                report_data.append(
                    {
                        "Student Name": item.student_name,
                        "Part Name": item.part_name,
                        "IPN": item.internal_part_number,
                        "MPN": item.mpn,
                        "SKU": item.sku,
                        "Requested": requested,
                        "Allocated": allocated,
                        "Shortfall": shortfall,
                    }
                )

        with open(filepath, mode="w", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "Student Name",
                    "Part Name",
                    "IPN",
                    "MPN",
                    "SKU",
                    "Requested",
                    "Allocated",
                    "Shortfall",
                ],
            )
            writer.writeheader()
            writer.writerows(report_data)

        return report_data, shortfalls_by_pk

    def _get_preferred_supplier_part(
        self, part_pk: int, supplier_id: int
    ) -> Optional[SupplierPart]:
        """Finds the best SupplierPart for a given base part and supplier."""
        # Try to find a direct match for this supplier first
        sp_list = SupplierPart.list(self.api, part=part_pk, supplier=supplier_id)
        if sp_list:
            return sp_list[0]  # Simplest: pick the first one found
        return None

    def create_purchase_order(
        self, supplier_id: int, shortfalls: Dict[int, float]
    ) -> Optional[PurchaseOrder]:
        """Creates a Draft Purchase Order in InvenTree for all shortages."""
        # Only create PO if there are actual shortfalls
        valid_shortfalls = {pk: qty for pk, qty in shortfalls.items() if qty > 0}
        if not valid_shortfalls:
            return None

        # 1. Create the PO Header
        po_data = {
            "supplier": supplier_id,
            "description": "Classroom Procurement - Student Carts",
        }
        po = PurchaseOrder.create(self.api, data=po_data)
        if isinstance(po, list):
            po = po[0]

        # 2. Add Line Items
        for part_pk, quantity in valid_shortfalls.items():
            sp = self._get_preferred_supplier_part(part_pk, supplier_id)
            if sp:
                line_data = {"order": po.pk, "part": sp.pk, "quantity": quantity}
                PurchaseOrderLineItem.create(self.api, data=line_data)
            else:
                print(
                    f"Warning: No SupplierPart found for Part {part_pk} and Supplier {supplier_id}. Skipping PO line."
                )

        return po
