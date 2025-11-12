"""
Part synchronization service
"""

from typing import Optional

from .config import Config
from .inventree_client import InvenTreeClient
from .suppliers import DigikeyClient, MouserClient, PartInfo, SupplierClient


class SyncService:
    """Service for synchronizing parts from suppliers to InvenTree"""
    
    def __init__(self, config: Config):
        self.config = config
        config.validate()
        
        # Initialize InvenTree client
        self.inventree = InvenTreeClient(config.inventree)
        
        # Initialize supplier clients
        self.suppliers: dict[str, SupplierClient] = {}
        
        if config.digikey:
            self.suppliers["digikey"] = DigikeyClient(config.digikey)
        
        if config.mouser:
            self.suppliers["mouser"] = MouserClient(config.mouser)
    
    def get_part_from_supplier(
        self,
        part_number: str,
        supplier: Optional[str] = None
    ) -> Optional[tuple[str, PartInfo]]:
        """
        Get part information from a supplier
        
        Args:
            part_number: Part number to search for
            supplier: Specific supplier to search (None = try all)
            
        Returns:
            Tuple of (supplier_name, PartInfo) if found, None otherwise
        """
        if supplier:
            # Try specific supplier
            supplier_lower = supplier.lower()
            if supplier_lower in self.suppliers:
                part_info = self.suppliers[supplier_lower].get_part_info(part_number)
                if part_info:
                    return (supplier_lower, part_info)
        else:
            # Try all suppliers in order
            for supplier_name, supplier_client in self.suppliers.items():
                part_info = supplier_client.get_part_info(part_number)
                if part_info:
                    return (supplier_name, part_info)
        
        return None
    
    def sync_part(
        self,
        part_number: str,
        supplier: Optional[str] = None
    ) -> Optional[dict]:
        """
        Sync a part from supplier to InvenTree
        
        Args:
            part_number: Part number to sync
            supplier: Specific supplier to use (None = try all)
            
        Returns:
            Dictionary with sync results or None if part not found
        """
        # Get part info from supplier
        result = self.get_part_from_supplier(part_number, supplier)
        
        if not result:
            return None
        
        supplier_name, part_info = result
        
        # Sync to InvenTree
        part, supplier_part = self.inventree.sync_part(part_info)
        
        return {
            "success": True,
            "supplier": supplier_name,
            "manufacturer": part_info.manufacturer_name,
            "manufacturer_part_number": part_info.manufacturer_part_number,
            "supplier_part_number": part_info.supplier_part_number,
            "inventree_part_id": part.pk,
            "inventree_supplier_part_id": supplier_part.pk,
            "description": part_info.description
        }
    
    def create_assembly_part(self, part_number: str) -> Optional[dict]:
        """
        Create an assembly part in InvenTree
        
        Args:
            part_number: Part number for the assembly
            
        Returns:
            Dictionary with part info or None if failed
        """
        return self.inventree.create_assembly_part(part_number)
    
    def add_bom_item(
        self,
        assembly_part_id: int,
        sub_part_id: int,
        quantity: float,
        reference: str = ""
    ) -> Optional[dict]:
        """
        Add a BOM item to an assembly
        
        Args:
            assembly_part_id: ID of the assembly part
            sub_part_id: ID of the sub-part to add
            quantity: Quantity required
            reference: Reference designators (optional)
            
        Returns:
            Dictionary with BOM item info or None if failed
        """
        return self.inventree.add_bom_item(assembly_part_id, sub_part_id, quantity, reference)
