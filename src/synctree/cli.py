"""
Command-line interface for SyncTree
"""

import csv
from pathlib import Path
from typing import Optional

import typer
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
)
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
        typer.Option(
            "--version",
            callback=version_callback,
            is_eager=True,
            help="Show version and exit",
        ),
    ] = None,
):
    """SyncTree - Sync supplier part information to InvenTree"""
    pass


@app.command()
def add(
    part_number: Annotated[
        str,
        typer.Argument(
            help="Part number to add (manufacturer or supplier part number)"
        ),
    ],
    supplier: Annotated[
        Optional[str],
        typer.Option(
            "--supplier",
            "-s",
            help="Specific supplier to use (default: try all configured suppliers)",
            case_sensitive=False,
        ),
    ] = None,
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Show detailed output")
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
        typer.echo(
            f"Error: Invalid supplier '{supplier}'. Must be 'digikey' or 'mouser'",
            err=True,
        )
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
        typer.echo("\n✅ Successfully synced part to InvenTree!")
        typer.echo("\n📦 Part Information:")
        typer.echo(f"   Manufacturer: {result['manufacturer']}")
        typer.echo(f"   MPN: {result['manufacturer_part_number']}")
        typer.echo(f"   Supplier: {result['supplier']}")
        typer.echo(f"   SKU: {result['supplier_part_number']}")

        if verbose:
            typer.echo("\n📝 Details:")
            typer.echo(f"   Description: {result['description']}")
            typer.echo(f"   InvenTree Part ID: {result['inventree_part_id']}")
            typer.echo(
                f"   InvenTree Supplier Part ID: {result['inventree_supplier_part_id']}"
            )

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
def bom(
    part_number: Annotated[
        str, typer.Argument(help="Part number to create in InvenTree")
    ],
    bom_file: Annotated[
        Path, typer.Argument(help="Path to TSV or CSV file with BOM data")
    ],
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Show detailed output")
    ] = False,
):
    """
    Create a part and add BOM items from a TSV or CSV file

    Creates a new part in InvenTree with the given PART_NUMBER and adds all items
    from the BOM file as bill of materials. The file should have columns for:
    - Supplier (or Supplier Name)
    - SPN (Supplier Part Number or SKU)
    - MPN (Manufacturer Part Number)
    - Qty (Quantity)
    - Designators (optional)

    Lines without MPN or SPN will be skipped.

    Examples:

        synctree bom MY-ASSEMBLY-001 total_bom.tsv

        synctree bom MY-PCB-REV2 bom.csv --verbose
    """
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

        # Check if file exists
        if not bom_file.exists():
            typer.echo(f"❌ Error: File not found: {bom_file}", err=True)
            raise typer.Exit(1)

        # Create sync service
        service = SyncService(config)

        # Create the assembly part
        typer.echo(f"Creating assembly part: {part_number}")
        assembly_result = service.create_assembly_part(part_number)

        if not assembly_result:
            typer.echo("❌ Failed to create assembly part", err=True)
            raise typer.Exit(1)

        typer.echo(
            f"✅ Created assembly part (ID: {assembly_result['inventree_part_id']})"
        )

        # Read BOM file
        typer.echo(f"\nReading BOM file: {bom_file}")

        # Determine delimiter based on file extension
        delimiter = "\t" if bom_file.suffix.lower() == ".tsv" else ","

        bom_items = []
        skipped_items = []

        with open(bom_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter=delimiter)
            for row_num, row in enumerate(reader, start=2):  # Start at 2 (1 for header)
                # Get values with flexible column names
                supplier = row.get("Supplier") or row.get("Supplier Name", "").strip()
                spn = row.get("SPN") or row.get("SKU", "").strip()
                mpn = row.get("MPN") or row.get("Manufacturer Part Number", "").strip()
                qty = row.get("Qty") or row.get("Quantity", "1").strip()
                designators = row.get("Designators", "").strip()

                # Skip if no MPN or SPN
                if not mpn and not spn:
                    skipped_items.append(f"Row {row_num}: No MPN or SPN")
                    continue

                # Parse quantity
                try:
                    quantity = float(qty) if qty else 1.0
                except ValueError:
                    quantity = 1.0

                bom_items.append(
                    {
                        "supplier": supplier,
                        "spn": spn,
                        "mpn": mpn,
                        "quantity": quantity,
                        "designators": designators,
                        "row": row_num,
                    }
                )

        typer.echo(f"Found {len(bom_items)} items to process")
        if skipped_items:
            typer.echo(f"Skipped {len(skipped_items)} items without MPN/SPN:")
            for item in skipped_items[:5]:  # Show first 5
                typer.echo(f"  - {item}")
            if len(skipped_items) > 5:
                typer.echo(f"  ... and {len(skipped_items) - 5} more")

        # Process each BOM item
        typer.echo("\nProcessing BOM items...")
        success_count = 0
        error_count = 0

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
        ) as progress:
            task = progress.add_task("Processing BOM items", total=len(bom_items))

            for idx, item in enumerate(bom_items, start=1):
                try:
                    # Try to find/sync the part
                    part_number_to_sync = item["spn"] if item["spn"] else item["mpn"]
                    supplier_name = (
                        item["supplier"].lower() if item["supplier"] else None
                    )

                    if verbose:
                        progress.console.print(
                            f"\n[{idx}/{len(bom_items)}] Processing: {part_number_to_sync}"
                        )

                    # Sync the component part
                    result = service.sync_part(part_number_to_sync, supplier_name)

                    if not result:
                        progress.console.print(
                            f"  ❌ Part not found: {part_number_to_sync}", style="red"
                        )
                        error_count += 1
                        progress.update(task, advance=1)
                        continue

                    # Add to BOM
                    bom_result = service.add_bom_item(
                        assembly_part_id=assembly_result["inventree_part_id"],
                        sub_part_id=result["inventree_part_id"],
                        quantity=item["quantity"],
                        reference=item["designators"],
                    )

                    if bom_result:
                        if verbose:
                            progress.console.print(
                                f"  ✅ Added to BOM: {result['manufacturer_part_number']}"
                            )
                        success_count += 1
                    else:
                        progress.console.print(
                            f"  ⚠️  Failed to add to BOM: {part_number_to_sync}",
                            style="yellow",
                        )
                        error_count += 1

                    progress.update(task, advance=1)

                except Exception as e:
                    progress.console.print(
                        f"  ❌ Error processing item: {e}", style="red"
                    )
                    if verbose:
                        import traceback

                        progress.console.print(traceback.format_exc())
                    error_count += 1
                    progress.update(task, advance=1)

        # Summary
        typer.echo("\n\n✅ BOM processing complete!")
        typer.echo("\n📊 Summary:")
        typer.echo(f"   Assembly Part: {part_number}")
        typer.echo(f"   InvenTree Part ID: {assembly_result['inventree_part_id']}")
        typer.echo(f"   Successfully added: {success_count} items")
        if error_count > 0:
            typer.echo(f"   Failed: {error_count} items")

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
def sync(
    supplier: Annotated[
        Optional[str],
        typer.Option(
            "--supplier",
            "-s",
            help="Specific supplier to sync (default: all configured suppliers)",
            case_sensitive=False,
        ),
    ] = None,
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Show detailed output")
    ] = False,
):
    """
    Sync all supplier parts with supplier systems

    Retrieves all supplier parts from InvenTree and checks them against the
    supplier APIs to verify that pricing and active status are up to date.
    Updates InvenTree with any changes found.

    Examples:

        synctree sync

        synctree sync --supplier digikey

        synctree sync --verbose
    """
    # Validate supplier choice if provided
    if supplier and supplier.lower() not in ["digikey", "mouser"]:
        typer.echo(
            f"Error: Invalid supplier '{supplier}'. Must be 'digikey' or 'mouser'",
            err=True,
        )
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
        typer.echo("🔄 Starting supplier part synchronization...")
        if supplier:
            typer.echo(f"   Syncing supplier: {supplier}")
        else:
            typer.echo("   Syncing all configured suppliers")

        # Track statistics
        stats = {"total": 0, "up_to_date": 0, "updated": 0, "not_found": 0, "errors": 0}

        # Process all supplier parts
        typer.echo("\nProcessing supplier parts...")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
        ) as progress:
            # Start with indeterminate progress since we don't know total count yet
            task = progress.add_task("Syncing supplier parts", total=None)

            for result in service.sync_all_supplier_parts(supplier):
                stats["total"] += 1
                progress.update(task, total=stats["total"], completed=stats["total"])

                status = result.get("status", "unknown")
                sku = result.get("sku", "unknown")
                supplier_name = result.get("supplier", "unknown")

                if status == "up_to_date":
                    stats["up_to_date"] += 1
                    if verbose:
                        progress.console.print(
                            f"  ✓ {supplier_name}: {sku} - {result.get('message')}"
                        )

                elif status == "updated":
                    stats["updated"] += 1
                    changes = result.get("changes", {})
                    change_summary = ", ".join(changes.keys())
                    progress.console.print(
                        f"  🔄 {supplier_name}: {sku} - Updated: {change_summary}"
                    )
                    if verbose:
                        for field, change in changes.items():
                            progress.console.print(
                                f"      {field}: {change.get('old')} → {change.get('new')}"
                            )

                elif status == "not_found":
                    stats["not_found"] += 1
                    progress.console.print(
                        f"  ⚠️  {supplier_name}: {sku} - {result.get('message')}"
                    )

                elif status == "error" or status == "update_failed":
                    stats["errors"] += 1
                    progress.console.print(
                        f"  ❌ {supplier_name}: {sku} - {result.get('message')}"
                    )
                    if verbose:
                        import traceback

                        progress.console.print(
                            f"      Error details: {result.get('message')}"
                        )

        # Summary
        typer.echo("\n\n✅ Synchronization complete!")
        typer.echo("\n📊 Summary:")
        typer.echo(f"   Total parts processed: {stats['total']}")
        typer.echo(f"   Up to date: {stats['up_to_date']}")
        typer.echo(f"   Updated: {stats['updated']}")
        if stats["not_found"] > 0:
            typer.echo(f"   Not found in supplier: {stats['not_found']}")
        if stats["errors"] > 0:
            typer.echo(f"   Errors: {stats['errors']}")

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
