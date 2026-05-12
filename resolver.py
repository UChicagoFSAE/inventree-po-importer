from typing import List, Dict, Optional
from models import LineItem
from inventree.company import SupplierPart, ManufacturerPart, Company
from inventree.part import Part, PartCategory


class Resolver:
    def __init__(self, api):
        self.api = api
        self.part_cache: Dict[int, Part] = {}

    def resolve_items(self, items: List[LineItem], supplier_id: int):
        """Enriches a list of LineItems with InvenTree PKs."""
        for item in items:
            self.resolve_item(item, supplier_id)

    def search_parts(self, query: str, limit: int = 5) -> List[Part]:
        """Search for parts in InvenTree."""
        return Part.list(self.api, search=query, limit=limit)

    def search_categories(self, query: str, limit: int = 5) -> List[PartCategory]:
        """Search for part categories in InvenTree."""
        return PartCategory.list(self.api, search=query, limit=limit)

    def search_manufacturers(self, query: str, limit: int = 5) -> List[Company]:
        """Search for companies that are manufacturers."""
        return Company.list(self.api, search=query, is_manufacturer=True, limit=limit)

    def create_manufacturer(self, name: str) -> Company:
        """Create a new manufacturer company."""
        return Company.create(self.api, data={"name": name, "is_manufacturer": True})

    def create_new_part(
        self,
        item: LineItem,
        name: str,
        description: str,
        category_pk: int,
        supplier_id: int,
        manufacturer_pk: Optional[int] = None,
    ) -> int:
        """Create a new Part and associated linkage."""
        # 1. Create Base Part
        part_data = {
            "name": name,
            "description": description,
            "category": category_pk,
            "active": True,
        }
        new_part = Part.create(self.api, data=part_data)
        if isinstance(new_part, list):
            new_part = new_part[0]

        # 2. Link Manufacturer Part if manufacturer provided
        manufacturer_part_pk = None
        if manufacturer_pk:
            mp_data = {
                "part": new_part.pk,
                "manufacturer": manufacturer_pk,
                "MPN": item.mpn,
            }
            new_mp = ManufacturerPart.create(self.api, data=mp_data)
            if isinstance(new_mp, list):
                new_mp = new_mp[0]
            manufacturer_part_pk = new_mp.pk

        # 3. Create Supplier Part
        sp_data = {
            "part": new_part.pk,
            "supplier": supplier_id,
            "SKU": item.sku,
            "manufacturer_part": manufacturer_part_pk,
        }
        new_sp = SupplierPart.create(self.api, data=sp_data)
        if isinstance(new_sp, list):
            new_sp = new_sp[0]

        # Store supplier_part_pk in item for stock creation
        item.supplier_part_pk = new_sp.pk

        return new_part.pk

    def link_manual_part(
        self, item: LineItem, part_pk: int, status_message: str = "Resolved (Manual)"
    ):
        """Manually link an item to a part and fetch metadata."""
        item.base_part_pk = part_pk
        item.resolution_status = status_message
        self._fetch_part_metadata(item)

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
