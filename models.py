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
    resolution_status: str = "Pending"
    error_message: Optional[str] = None
