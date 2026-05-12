import click
from tabulate import tabulate
from config import get_api
from parser import parse_csv
from resolver import Resolver
from stock_manager import StockManager


@click.command()
@click.argument("input_csv", type=click.Path(exists=True))
@click.option(
    "--supplier-id",
    required=True,
    type=int,
    help="InvenTree ID for the supplier (e.g. DigiKey)",
)
@click.option(
    "--location-id",
    required=True,
    type=int,
    help="InvenTree ID for the destination stock location",
)
def importer(input_csv, supplier_id, location_id):
    """Reconcile a supplier CSV and import stock into InvenTree."""

    click.echo("Connecting to InvenTree...")
    try:
        api = get_api()
    except Exception as e:
        click.secho(f"Error: Could not connect to InvenTree API: {e}", fg="red")
        return

    click.echo(f"Parsing {input_csv}...")
    items = parse_csv(input_csv)
    click.echo(f"Found {len(items)} items in CSV.")

    click.echo(f"Reconciling items (Supplier ID: {supplier_id})...")
    resolver = Resolver(api)

    with click.progressbar(items, label="Resolving") as bar:
        for item in bar:
            resolver.resolve_item(item, supplier_id)

    # Prepare table data for verification
    table_data = []
    for item in items:
        table_data.append(
            [
                item.index,
                item.sku,
                item.mpn,
                (item.description[:30] + "..")
                if len(item.description) > 30
                else item.description,
                item.customer_reference if item.customer_reference else "---",
                item.part_name if item.part_name else "---",
                (item.part_description[:30] + "..")
                if item.part_description and len(item.part_description) > 30
                else (item.part_description or "---"),
                item.resolution_status,
            ]
        )

    headers = ["#", "SKU", "MPN", "CSV Desc", "CSV Ref", "IV Name", "IV Desc", "Status"]
    click.echo("\nReconciliation & Verification Table:")
    click.echo(tabulate(table_data, headers=headers, tablefmt="grid"))

    # Summary stats
    resolved_items = [i for i in items if "Resolved" in i.resolution_status]
    resolved_count = len(resolved_items)
    click.echo(
        f"\nTotal: {len(items)} | Resolved: {resolved_count} | Failed: {len(items) - resolved_count}"
    )

    if resolved_count == 0:
        click.secho(
            "No items resolved. Cannot proceed with stock creation.", fg="yellow"
        )
        return

    # Prompt for stock creation
    if click.confirm(
        f"\nDo you want to create stock items for the {resolved_count} resolved parts in location {location_id}?"
    ):
        click.echo("Creating stock items...")
        manager = StockManager(api)
        results = manager.create_stock(resolved_items, location_id)

        # Prepare post-creation summary table
        creation_table = []
        success_count = 0
        for res in results:
            if res["status"] == "Success":
                success_count += 1

            creation_table.append(
                [
                    res["status"],
                    res["ipn"],
                    res["name"],
                    res["qty"],
                    (res["desc"][:30] + "..")
                    if res["desc"] and len(res["desc"]) > 30
                    else (res["desc"] or "---"),
                    res["sku"],
                    res["mpn"],
                    res["pk"] if res["pk"] else "---",
                ]
            )

        click.echo("\nStock Creation Results:")
        headers = [
            "Status",
            "Internal PN",
            "Internal Name",
            "Qty",
            "Internal Desc",
            "SKU",
            "MPN",
            "Stock PK",
        ]
        click.echo(tabulate(creation_table, headers=headers, tablefmt="grid"))

        fail_count = len(results) - success_count
        if success_count > 0:
            click.secho(
                f"Successfully created {success_count} stock items.", fg="green"
            )
        if fail_count > 0:
            click.secho(
                f"Failed to create {fail_count} stock items.", fg="red", bold=True
            )
    else:
        click.echo("Stock creation cancelled.")


if __name__ == "__main__":
    importer()
