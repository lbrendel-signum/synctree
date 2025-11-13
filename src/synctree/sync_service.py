"""
Part synchronization service
"""

from typing import Optional

from .config import Config
from .inventree_client import InvenTreeClient
from .suppliers import DigikeyClient, MouserClient, PartInfo, SupplierClient
from inventree.company import SupplierPriceBreak

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

    def sync_all_supplier_parts(self, supplier_name: Optional[str] = None):
        """
        Sync all supplier parts from InvenTree with supplier systems

        Retrieves all supplier parts from InvenTree and checks them against
        the supplier APIs to verify pricing and active status are up to date.

        Args:
            supplier_name: Specific supplier to sync (None = all configured suppliers)

        Yields:
            Dictionary with sync status for each part
        """
        # Get all supplier parts from InvenTree
        supplier_parts = self.inventree.get_all_supplier_parts(supplier_name)

        for inventree_supplier_part in supplier_parts:
            try:
                # Get the supplier company name
                supplier_company = inventree_supplier_part.get('supplier_detail', {}).get('name', '').lower()

                # Skip if not in configured suppliers
                if supplier_company not in self.suppliers:
                    continue

                # Get supplier part number
                sku = inventree_supplier_part.get('SKU', '')
                if not sku:
                    continue

                # Query the supplier API
                supplier_client = self.suppliers[supplier_company]
                part_info = supplier_client.get_part_info(sku)

                if not part_info:
                    yield {
                        'sku': sku,
                        'supplier': supplier_company,
                        'status': 'not_found',
                        'inventree_id': inventree_supplier_part.get('pk'),
                        'message': 'Part not found in supplier system'
                    }
                    continue

                # Compare data
                changes = self._compare_supplier_part_data(inventree_supplier_part, part_info)

                if changes:
                    # Update InvenTree with new data
                    updated = self.inventree.update_supplier_part(
                        inventree_supplier_part.get('pk'),
                        part_info
                    )

                    yield {
                        'sku': sku,
                        'supplier': supplier_company,
                        'status': 'updated' if updated else 'update_failed',
                        'inventree_id': inventree_supplier_part.get('pk'),
                        'changes': changes,
                        'message': f"Updated {len(changes)} fields"
                    }
                else:
                    yield {
                        'sku': sku,
                        'supplier': supplier_company,
                        'status': 'up_to_date',
                        'inventree_id': inventree_supplier_part.get('pk'),
                        'message': 'No changes needed'
                    }

            except Exception as e:
                yield {
                    'sku': inventree_supplier_part.get('SKU', 'unknown'),
                    'supplier': supplier_company if 'supplier_company' in locals() else 'unknown',
                    'status': 'error',
                    'inventree_id': inventree_supplier_part.get('pk'),
                    'message': str(e)
                }

    def _compare_supplier_part_data(self, inventree_part: dict, supplier_info: PartInfo) -> dict:
        """
        Compare InvenTree supplier part with supplier API data

        Returns:
            Dictionary of fields that differ
        """
        changes = {}

        # Check active status
        if inventree_part.get('active') != supplier_info.is_active:
            changes['active'] = {
                'old': inventree_part.get('active'),
                'new': supplier_info.is_active
            }

        # Check pricing (compare latest price breaks)
        if supplier_info.pricing:
            inventree_prices = SupplierPriceBreak.list(self.inventree.api,
                part=inventree_part.get('pk'))
            # Simple check - if pricing data exists and doesn't match, flag for update
            if not inventree_prices or self._pricing_differs(inventree_prices, supplier_info.pricing):
                changes['pricing'] = {
                    'old': len(inventree_prices),
                    'new': len(supplier_info.pricing)
                }

        return changes

    def _pricing_differs(self, inventree_prices: list, supplier_pricing: dict) -> bool:
        """Check if pricing data differs between InvenTree and supplier"""
        if len(inventree_prices) != len(supplier_pricing):
            return True

        # Create a dict from inventree prices for comparison
        inventree_price_dict = {}
        for price_break in inventree_prices:
            qty = price_break.quantity
            price = price_break.price
            inventree_price_dict[qty] = price

        # Compare with supplier pricing
        for qty, price in supplier_pricing.items():
            if qty not in inventree_price_dict:
                return True
            # Allow small floating point differences
            if abs(inventree_price_dict[qty] - price) > 0.01:
                return True

        return False
