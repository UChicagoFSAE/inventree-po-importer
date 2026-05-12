from dataclasses import dataclass
from typing import Optional


@dataclass
class LineItem:
    # Parsed data from CSV
    index: int
    sku: str
    mpn: str
    quantity: float
    unit_price: float
    description: str
    customer_reference: Optional[str] = None

    # Resolved data from InvenTree
    supplier_part_pk: Optional[int] = None
    base_part_pk: Optional[int] = None
    part_name: Optional[str] = None
    part_description: Optional[str] = None
    internal_part_number: Optional[str] = None
    resolution_status: str = "Pending"
    error_message: Optional[str] = None
