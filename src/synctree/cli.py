"""
Command-line interface for SyncTree
"""

import sys
from typing import Optional

import click

from . import __version__
from .config import Config
from .sync_service import SyncService


@click.group()
@click.version_option(version=__version__)
def main():
    """SyncTree - Sync supplier part information to InvenTree"""
    pass


@main.command()
@click.argument("part_number")
@click.option(
    "--supplier",
    "-s",
    type=click.Choice(["digikey", "mouser"], case_sensitive=False),
    help="Specific supplier to use (default: try all configured suppliers)"
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Show detailed output"
)
def sync(part_number: str, supplier: Optional[str], verbose: bool):
    """
    Sync a part to InvenTree by part number
    
    PART_NUMBER can be either a manufacturer part number or a supplier part number.
    The tool will search configured suppliers and sync the part to InvenTree,
    including manufacturer and supplier information.
    
    Examples:
    
        synctree sync 296-6501-1-ND
        
        synctree sync CRCW080510K0FKEA --supplier digikey
        
        synctree sync STM32F103C8T6 --verbose
    """
    try:
        # Load configuration
        config = Config.from_env()
        
        # Validate configuration
        try:
            config.validate()
        except ValueError as e:
            click.echo(f"Configuration error: {e}", err=True)
            click.echo("\nPlease set the required environment variables:", err=True)
            click.echo("  - INVENTREE_SERVER_URL: Your InvenTree server URL", err=True)
            click.echo("  - INVENTREE_TOKEN: Your InvenTree API token", err=True)
            click.echo("\nFor suppliers, set at least one:", err=True)
            click.echo("  Digikey:", err=True)
            click.echo("    - DIGIKEY_CLIENT_ID", err=True)
            click.echo("    - DIGIKEY_CLIENT_SECRET", err=True)
            click.echo("  Mouser:", err=True)
            click.echo("    - MOUSER_PART_API_KEY", err=True)
            sys.exit(1)
        
        # Create sync service
        service = SyncService(config)
        
        # Display info
        click.echo(f"Searching for part: {part_number}")
        if supplier:
            click.echo(f"Using supplier: {supplier}")
        
        # Sync the part
        result = service.sync_part(part_number, supplier)
        
        if not result:
            click.echo(f"❌ Part '{part_number}' not found", err=True)
            if supplier:
                click.echo(f"   Searched in: {supplier}", err=True)
            else:
                configured = ", ".join(service.suppliers.keys())
                click.echo(f"   Searched in: {configured}", err=True)
            sys.exit(1)
        
        # Display results
        click.echo(f"\n✅ Successfully synced part to InvenTree!")
        click.echo(f"\n📦 Part Information:")
        click.echo(f"   Manufacturer: {result['manufacturer']}")
        click.echo(f"   MPN: {result['manufacturer_part_number']}")
        click.echo(f"   Supplier: {result['supplier']}")
        click.echo(f"   SKU: {result['supplier_part_number']}")
        
        if verbose:
            click.echo(f"\n📝 Details:")
            click.echo(f"   Description: {result['description']}")
            click.echo(f"   InvenTree Part ID: {result['inventree_part_id']}")
            click.echo(f"   InvenTree Supplier Part ID: {result['inventree_supplier_part_id']}")
        
    except KeyboardInterrupt:
        click.echo("\n\nOperation cancelled by user", err=True)
        sys.exit(130)
    except Exception as e:
        click.echo(f"\n❌ Error: {e}", err=True)
        if verbose:
            import traceback
            click.echo("\nTraceback:", err=True)
            click.echo(traceback.format_exc(), err=True)
        sys.exit(1)


@main.command()
def config():
    """Show current configuration status"""
    try:
        cfg = Config.from_env()
        
        click.echo("Configuration Status:\n")
        
        # InvenTree
        if cfg.inventree:
            click.echo("✅ InvenTree:")
            click.echo(f"   Server: {cfg.inventree.server_url}")
            click.echo(f"   Token: {'*' * 10}")
        else:
            click.echo("❌ InvenTree: Not configured")
            click.echo("   Set: INVENTREE_SERVER_URL, INVENTREE_TOKEN")
        
        # Digikey
        click.echo()
        if cfg.digikey:
            click.echo("✅ Digikey:")
            click.echo(f"   Client ID: {cfg.digikey.client_id[:8]}...")
            click.echo(f"   Storage: {cfg.digikey.storage_path}")
            click.echo(f"   Sandbox: {cfg.digikey.sandbox}")
        else:
            click.echo("❌ Digikey: Not configured")
            click.echo("   Set: DIGIKEY_CLIENT_ID, DIGIKEY_CLIENT_SECRET")
        
        # Mouser
        click.echo()
        if cfg.mouser:
            click.echo("✅ Mouser:")
            click.echo(f"   API Key: {cfg.mouser.part_api_key[:8]}...")
        else:
            click.echo("❌ Mouser: Not configured")
            click.echo("   Set: MOUSER_PART_API_KEY")
        
    except Exception as e:
        click.echo(f"Error loading configuration: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
