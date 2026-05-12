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

    def print_verification_table(items_list):
        table_data = []
        for item in items_list:
            status = item.resolution_status
            if "Resolved" in status:
                styled_status = click.style(status, fg="green")
            elif status in ["Not Found", "Error"]:
                styled_status = click.style(status, fg="red", bold=True)
            else:
                styled_status = status

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
                    styled_status,
                ]
            )
        headers = [
            "#",
            "SKU",
            "MPN",
            "CSV Desc",
            "CSV Ref",
            "IV Name",
            "IV Desc",
            "Status",
        ]
        click.echo("\nReconciliation & Verification Table:")
        click.echo(tabulate(table_data, headers=headers, tablefmt="grid"))

        resolved_count = len(
            [i for i in items_list if "Resolved" in i.resolution_status]
        )
        failed_count = len(items_list) - resolved_count

        click.echo(f"\nTotal: {len(items_list)} | ", nl=False)
        click.secho(f"Resolved: {resolved_count}", fg="green", nl=False)
        click.echo(" | ", nl=False)
        click.secho(
            f"Failed: {failed_count}", fg="red" if failed_count > 0 else "white"
        )

        return resolved_count

    # Initial table display
    print_verification_table(items)

    # Manual fallback for unresolved items
    unresolved = [i for i in items if i.resolution_status in ["Not Found", "Error"]]
    if unresolved and click.confirm(
        f"\nFound {len(unresolved)} unresolved items. Resolve them manually?"
    ):
        for i, item in enumerate(unresolved):
            click.secho(
                f"\n--- Manual Resolution ({i+1}/{len(unresolved)}) ---",
                fg="cyan",
                bold=True,
            )
            # Display item context
            click.echo(f"CSV SKU: {item.sku}")
            click.echo(f"CSV MPN: {item.mpn}")
            click.echo(f"CSV Manufacturer: {item.manufacturer or 'N/A'}")
            click.echo(f"CSV Desc: {item.description}")
            click.echo(
                f"Qty: {item.quantity} | Price: {item.unit_price} | Ref: {item.customer_reference or 'N/A'}"
            )

            resolved = False
            query = item.mpn or item.description
            while not resolved:
                # Auto-search or custom search
                parts = resolver.search_parts(query)
                if parts:
                    click.echo("\nSearch Results:")
                    for idx, p in enumerate(parts):
                        click.echo(
                            f"  [{idx+1}] {p.name} (IPN: {getattr(p, 'IPN', '---')}) - {p.description[:50]}"
                        )
                else:
                    click.secho("No matching parts found in InvenTree.", fg="yellow")

                choice = click.prompt(
                    "\nSelect [1-5], [S]earch, [M]anual PK, [C]reate New, [X]kip",
                    type=str,
                    default="X",
                ).upper()

                if choice.isdigit() and 1 <= int(choice) <= len(parts):
                    selected_part = parts[int(choice) - 1]
                    resolver.link_manual_part(item, selected_part.pk)
                    resolved = True
                elif choice == "S":
                    query = click.prompt("Enter search term")
                elif choice == "M":
                    pk_val = click.prompt("Enter InvenTree Part PK or IPN")
                    try:
                        # Simple check: if it's an integer, assume PK. Otherwise, we'd need to search by IPN.
                        # For simplicity, let's try to fetch by PK first.
                        if pk_val.isdigit():
                            resolver.link_manual_part(item, int(pk_val))
                            resolved = True
                        else:
                            # Search by IPN
                            ipn_parts = resolver.search_parts(pk_val)
                            if ipn_parts and getattr(ipn_parts[0], "IPN", "") == pk_val:
                                resolver.link_manual_part(ipn_parts[0].pk)
                                resolved = True
                            else:
                                click.secho(
                                    f"Could not find part with IPN {pk_val}", fg="red"
                                )
                    except Exception as e:
                        click.secho(f"Error: {e}", fg="red")
                elif choice == "C":
                    # Create New flow
                    name = click.prompt("Part Name", default=item.mpn or item.sku)
                    desc = click.prompt("Part Description", default=item.description)

                    # Category selection
                    cat_resolved = False
                    cat_pk = None
                    while not cat_resolved:
                        cat_input = click.prompt("Enter Category PK or search term")
                        if cat_input.isdigit():
                            cat_pk = int(cat_input)
                            cat_resolved = True
                        else:
                            cats = resolver.search_categories(cat_input)
                            if cats:
                                for idx, c in enumerate(cats):
                                    click.echo(f"  [{idx+1}] {c.name} ({c.pathstring})")
                                cat_choice = click.prompt(
                                    "Select [1-5] or [S]earch again", default="S"
                                ).upper()
                                if cat_choice.isdigit() and 1 <= int(cat_choice) <= len(
                                    cats
                                ):
                                    cat_pk = cats[int(cat_choice) - 1].pk
                                    cat_resolved = True
                            else:
                                click.secho("No categories found.", fg="yellow")

                    # Manufacturer selection
                    mfr_pk = None
                    mfr_input = click.prompt(
                        "Enter Manufacturer Name/PK (leave blank to skip)",
                        default=item.manufacturer or "",
                        show_default=True if item.manufacturer else False,
                    )
                    if mfr_input:
                        if mfr_input.isdigit():
                            mfr_pk = int(mfr_input)
                        else:
                            mfrs = resolver.search_manufacturers(mfr_input)
                            if mfrs:
                                for idx, m in enumerate(mfrs):
                                    click.echo(f"  [{idx+1}] {m.name}")
                                mfr_choice = click.prompt(
                                    "Select [1-5], [S]earch again, or [N]ew manufacturer",
                                    default="N",
                                ).upper()
                                if mfr_choice.isdigit() and 1 <= int(mfr_choice) <= len(
                                    mfrs
                                ):
                                    mfr_pk = mfrs[int(mfr_choice) - 1].pk
                                elif mfr_choice == "N":
                                    new_mfr = resolver.create_manufacturer(mfr_input)
                                    mfr_pk = new_mfr.pk
                            else:
                                if click.confirm(
                                    f"Manufacturer '{mfr_input}' not found. Create it?"
                                ):
                                    new_mfr = resolver.create_manufacturer(mfr_input)
                                    mfr_pk = new_mfr.pk

                    try:
                        new_part_pk = resolver.create_new_part(
                            item, name, desc, cat_pk, supplier_id, mfr_pk
                        )
                        resolver.link_manual_part(
                            item, new_part_pk, "Resolved (Created)"
                        )
                        resolved = True
                    except Exception as e:
                        click.secho(f"Error creating part: {e}", fg="red")

                elif choice == "X":
                    resolved = True

        # Re-display table after manual resolution
        resolved_count = print_verification_table(items)
    else:
        resolved_count = len([i for i in items if "Resolved" in i.resolution_status])

    if resolved_count == 0:
        click.secho(
            "No items resolved. Cannot proceed with stock creation.", fg="yellow"
        )
        return

    resolved_items = [i for i in items if "Resolved" in i.resolution_status]

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
            status = res["status"]
            if status == "Success":
                success_count += 1
                styled_status = click.style(status, fg="green")
            else:
                styled_status = click.style(status, fg="red", bold=True)

            creation_table.append(
                [
                    styled_status,
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
