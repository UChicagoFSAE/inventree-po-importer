from typing import List, Dict
from models import LineItem
from inventree.company import SupplierPart, ManufacturerPart
from inventree.part import Part


class Resolver:
    def __init__(self, api):
        self.api = api
        self.part_cache: Dict[int, Part] = {}

    def resolve_items(self, items: List[LineItem], supplier_id: int):
        """Enriches a list of LineItems with InvenTree PKs."""
        for item in items:
            self.resolve_item(item, supplier_id)

    def _fetch_part_metadata(self, item: LineItem):
        """Fetches part name and description if a base_part_pk is present."""
        if not item.base_part_pk:
            return

        if item.base_part_pk in self.part_cache:
            p = self.part_cache[item.base_part_pk]
        else:
            p = Part(self.api, pk=item.base_part_pk)
            self.part_cache[item.base_part_pk] = p

        item.part_name = getattr(p, "name", "N/A")
        item.part_description = getattr(p, "description", "N/A")
        item.internal_part_number = getattr(p, "IPN", "---")

    def resolve_item(self, item: LineItem, supplier_id: int):
        # 1. Try SKU match (SupplierPart)
        try:
            # Note: InvenTree API list() returns a list of objects
            supplier_parts = SupplierPart.list(
                self.api, SKU=item.sku, supplier=supplier_id
            )

            if supplier_parts:
                sp = supplier_parts[0]
                item.supplier_part_pk = sp.pk
                item.base_part_pk = sp.part
                item.resolution_status = "Resolved (SKU)"
                self._fetch_part_metadata(item)
                return

            # 2. Try MPN match (ManufacturerPart)
            manufacturer_parts = ManufacturerPart.list(self.api, MPN=item.mpn)

            if manufacturer_parts:
                mp = manufacturer_parts[0]
                item.base_part_pk = mp.part
                item.resolution_status = "Resolved (MPN)"
                self._fetch_part_metadata(item)
                # Note: supplier_part_pk remains None as it's not a direct supplier match
                return

            item.resolution_status = "Not Found"

        except Exception as e:
            item.resolution_status = "Error"
            item.error_message = str(e)
