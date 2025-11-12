"""
Command-line interface for SyncTree
"""

import sys
from typing import Optional

import typer
from typing_extensions import Annotated

from . import __version__
from .config import Config
from .sync_service import SyncService

app = typer.Typer(help="SyncTree - Sync supplier part information to InvenTree")


def version_callback(value: bool):
    """Show version and exit"""
    if value:
        typer.echo(f"synctree, version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        Optional[bool],
        typer.Option("--version", callback=version_callback, is_eager=True, help="Show version and exit")
    ] = None,
):
    """SyncTree - Sync supplier part information to InvenTree"""
    pass


@app.command()
def add(
    part_number: Annotated[str, typer.Argument(help="Part number to add (manufacturer or supplier part number)")],
    supplier: Annotated[
        Optional[str],
        typer.Option(
            "--supplier",
            "-s",
            help="Specific supplier to use (default: try all configured suppliers)",
            case_sensitive=False
        )
    ] = None,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Show detailed output")
    ] = False,
):
    """
    Add a part to InvenTree by part number

    PART_NUMBER can be either a manufacturer part number or a supplier part number.
    The tool will search configured suppliers and add the part to InvenTree,
    including manufacturer and supplier information.

    Examples:

        synctree add 296-6501-1-ND

        synctree add CRCW080510K0FKEA --supplier digikey

        synctree add STM32F103C8T6 --verbose
    """
    # Validate supplier choice if provided
    if supplier and supplier.lower() not in ["digikey", "mouser"]:
        typer.echo(f"Error: Invalid supplier '{supplier}'. Must be 'digikey' or 'mouser'", err=True)
        raise typer.Exit(1)
    
    try:
        # Load configuration
        config = Config.from_env()

        # Validate configuration
        try:
            config.validate()
        except ValueError as e:
            typer.echo(f"Configuration error: {e}", err=True)
            typer.echo("\nPlease set the required environment variables:", err=True)
            typer.echo("  - INVENTREE_SERVER_URL: Your InvenTree server URL", err=True)
            typer.echo("  - INVENTREE_TOKEN: Your InvenTree API token", err=True)
            typer.echo("\nFor suppliers, set at least one:", err=True)
            typer.echo("  Digikey:", err=True)
            typer.echo("    - DIGIKEY_CLIENT_ID", err=True)
            typer.echo("    - DIGIKEY_CLIENT_SECRET", err=True)
            typer.echo("  Mouser:", err=True)
            typer.echo("    - MOUSER_PART_API_KEY", err=True)
            raise typer.Exit(1)

        # Create sync service
        service = SyncService(config)

        # Display info
        typer.echo(f"Searching for part: {part_number}")
        if supplier:
            typer.echo(f"Using supplier: {supplier}")

        # Sync the part
        result = service.sync_part(part_number, supplier)

        if not result:
            typer.echo(f"❌ Part '{part_number}' not found", err=True)
            if supplier:
                typer.echo(f"   Searched in: {supplier}", err=True)
            else:
                configured = ", ".join(service.suppliers.keys())
                typer.echo(f"   Searched in: {configured}", err=True)
            raise typer.Exit(1)

        # Display results
        typer.echo(f"\n✅ Successfully synced part to InvenTree!")
        typer.echo(f"\n📦 Part Information:")
        typer.echo(f"   Manufacturer: {result['manufacturer']}")
        typer.echo(f"   MPN: {result['manufacturer_part_number']}")
        typer.echo(f"   Supplier: {result['supplier']}")
        typer.echo(f"   SKU: {result['supplier_part_number']}")

        if verbose:
            typer.echo(f"\n📝 Details:")
            typer.echo(f"   Description: {result['description']}")
            typer.echo(f"   InvenTree Part ID: {result['inventree_part_id']}")
            typer.echo(f"   InvenTree Supplier Part ID: {result['inventree_supplier_part_id']}")

    except typer.Exit:
        raise
    except KeyboardInterrupt:
        typer.echo("\n\nOperation cancelled by user", err=True)
        raise typer.Exit(130)
    except Exception as e:
        typer.echo(f"\n❌ Error: {e}", err=True)
        if verbose:
            import traceback
            typer.echo("\nTraceback:", err=True)
            typer.echo(traceback.format_exc(), err=True)
        raise typer.Exit(1)


@app.command()
def config():
    """Show current configuration status"""
    try:
        cfg = Config.from_env()

        typer.echo("Configuration Status:\n")

        # InvenTree
        if cfg.inventree:
            typer.echo("✅ InvenTree:")
            typer.echo(f"   Server: {cfg.inventree.server_url}")
            typer.echo(f"   Token: {'*' * 10}")
        else:
            typer.echo("❌ InvenTree: Not configured")
            typer.echo("   Set: INVENTREE_SERVER_URL, INVENTREE_TOKEN")

        # Digikey
        typer.echo()
        if cfg.digikey:
            typer.echo("✅ Digikey:")
            typer.echo(f"   Client ID: {cfg.digikey.client_id[:8]}...")
            typer.echo(f"   Storage: {cfg.digikey.storage_path}")
            typer.echo(f"   Sandbox: {cfg.digikey.sandbox}")
        else:
            typer.echo("❌ Digikey: Not configured")
            typer.echo("   Set: DIGIKEY_CLIENT_ID, DIGIKEY_CLIENT_SECRET")

        # Mouser
        typer.echo()
        if cfg.mouser:
            typer.echo("✅ Mouser:")
            typer.echo(f"   API Key: {cfg.mouser.part_api_key[:8]}...")
        else:
            typer.echo("❌ Mouser: Not configured")
            typer.echo("   Set: MOUSER_PART_API_KEY")

    except Exception as e:
        typer.echo(f"Error loading configuration: {e}", err=True)
        raise typer.Exit(1)


if __name__ == "__main__":
    app()

