import click
import pandas as pd
from tabulate import tabulate
from config import get_api
from parser import parse_csv
from resolver import Resolver
from stock_manager import StockManager
from procurement_manager import ProcurementManager
from mapping_utils import (
    get_saved_mapping,
    save_mapping,
    detect_columns,
    REQUIRED_FIELDS,
)


from conventions import NamingConvention


@click.group()
def cli():
    """InvenTree PO Importer CLI."""
    pass


@cli.command()
@click.argument("input_csvs", type=click.Path(exists=True), nargs=-1)
@click.option(
    "--supplier-id",
    required=False,
    type=int,
    help="InvenTree ID for the supplier to create the PO for (e.g. Mouser)",
)
@click.option(
    "--output",
    default="allocations.csv",
    help="Path to save the allocation report CSV",
)
def process_carts(input_csvs, supplier_id, output):
    """Aggregate student carts, allocate stock, and generate a PO for shortages."""
    if not input_csvs:
        click.echo("Error: No input CSV files provided.")
        return

    click.echo("Connecting to InvenTree...")
    try:
        api = get_api()
    except Exception as e:
        click.secho(f"Error: Could not connect to InvenTree API: {e}", fg="red")
        return

    if not supplier_id:
        supplier_id = _select_supplier(api)

    all_items = []
    for csv_file in input_csvs:
        click.echo(f"Processing {csv_file}...")
        mapping = get_saved_mapping(supplier_id)
        if not mapping:
            click.echo(f"No saved mapping for supplier {supplier_id}. Detecting...")
            mapping = detect_columns(csv_file)
            # Basic validation
            missing = [f for f in REQUIRED_FIELDS if not mapping.get(f)]
            if missing:
                click.secho(
                    f"Warning: Skipping {csv_file} - missing fields: {missing}",
                    fg="yellow",
                )
                continue

        items = parse_csv(csv_file, mapping)
        all_items.extend(items)

    if not all_items:
        click.echo("No items found to process.")
        return

    click.echo(
        f"Reconciling {len(all_items)} total items across {len(input_csvs)} carts..."
    )
    resolver = Resolver(api)
    with click.progressbar(all_items, label="Resolving") as bar:
        for item in bar:
            resolver.resolve_item(item, supplier_id)

    # Manual fallback for unresolved items
    _print_verification_table(all_items)
    unresolved = [i for i in all_items if i.resolution_status in ["Not Found", "Error"]]
    if unresolved and click.confirm(
        f"\nFound {len(unresolved)} unresolved items. Resolve them manually?"
    ):
        _manual_resolution_loop(unresolved, resolver, supplier_id)
        _print_verification_table(all_items)

    resolved_items = [i for i in all_items if "Resolved" in i.resolution_status]
    if not resolved_items:
        click.secho(
            "No items were resolved. Cannot proceed with procurement.", fg="red"
        )
        return

    pm = ProcurementManager(api)
    click.echo(f"Generating allocation report to {output}...")
    report, shortfalls = pm.generate_report(resolved_items, output)

    click.echo(f"Report generated with {len(report)} allocation lines.")

    total_shortfall = sum(shortfalls.values())
    if total_shortfall > 0:
        if click.confirm(
            f"\nFound {len(shortfalls)} parts with shortages (Total: {total_shortfall}). Create a Draft PO for Supplier {supplier_id}?"
        ):
            po = pm.create_purchase_order(supplier_id, shortfalls)
            if po:
                click.secho(
                    f"Successfully created Draft Purchase Order PO#{po.pk}", fg="green"
                )
            else:
                click.secho("Failed to create Purchase Order.", fg="red")
    else:
        click.secho(
            "No shortages found. All items can be fulfilled from stock!", fg="green"
        )


@cli.command()
@click.argument("input_csv", type=click.Path(exists=True))
@click.option(
    "--supplier-id",
    required=False,
    type=int,
    help="InvenTree ID for the supplier (e.g. DigiKey)",
)
@click.option(
    "--location-id",
    required=False,
    type=int,
    help="InvenTree ID for the destination stock location",
)
def import_invoice(input_csv, supplier_id, location_id):
    """Reconcile a supplier CSV and import stock into InvenTree."""
    click.echo("Connecting to InvenTree...")
    try:
        api = get_api()
    except Exception as e:
        click.secho(f"Error: Could not connect to InvenTree API: {e}", fg="red")
        return

    if not supplier_id:
        supplier_id = _select_supplier(api)
    if not location_id:
        location_id = _select_location(api)

    _run_importer(input_csv, supplier_id, location_id, api=api)


def _print_verification_table(items_list):
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
                if item.description and len(item.description) > 30
                else (item.description or "---"),
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

    resolved_count = len([i for i in items_list if "Resolved" in i.resolution_status])
    failed_count = len(items_list) - resolved_count

    click.echo(f"\nTotal: {len(items_list)} | ", nl=False)
    click.secho(f"Resolved: {resolved_count}", fg="green", nl=False)
    click.echo(" | ", nl=False)
    click.secho(f"Failed: {failed_count}", fg="red" if failed_count > 0 else "white")

    return resolved_count


def _resolve_category(resolver):
    """Helper to resolve a category PK via search."""
    cat_input = click.prompt("Enter Category PK or search term")
    if cat_input.isdigit():
        return int(cat_input), False

    cats = resolver.search_categories(cat_input)
    if cats:
        # Check for exact match
        for c in cats:
            if c.name.lower() == cat_input.lower():
                click.secho(
                    f"  Exact category match found: {c.name}. Auto-selecting...",
                    fg="cyan",
                )
                return c.pk, True

        for idx, c in enumerate(cats):
            click.echo(f"  [{idx + 1}] {c.name} ({c.pathstring})")

        cat_choice = click.prompt(
            "Select [1-N] or [S]earch again", default="1", show_default=True
        ).upper()

        if cat_choice.isdigit() and 1 <= int(cat_choice) <= len(cats):
            return cats[int(cat_choice) - 1].pk, False
        else:
            return _resolve_category(resolver)
    else:
        click.secho("No categories found.", fg="yellow")
        return _resolve_category(resolver)


def _resolve_manufacturer(resolver, default_name=None):
    """Helper to resolve a manufacturer PK via search or creation."""
    mfr_input = click.prompt(
        "Enter Manufacturer Name/PK (leave blank to skip)",
        default=default_name or "",
        show_default=True if default_name else False,
    )
    if not mfr_input:
        return None, False

    if mfr_input.isdigit():
        return int(mfr_input), False

    mfrs = resolver.search_manufacturers(mfr_input)
    if mfrs:
        # Check for exact match
        for m in mfrs:
            if m.name.lower() == mfr_input.lower():
                click.secho(
                    f"  Exact manufacturer match found: {m.name}. Auto-selecting...",
                    fg="cyan",
                )
                return m.pk, True

        for idx, m in enumerate(mfrs):
            click.echo(f"  [{idx + 1}] {m.name}")

        mfr_choice = click.prompt(
            "Select [1-N], [S]earch again, or [N]ew manufacturer",
            default="1",
            show_default=True,
        ).upper()

        if mfr_choice.isdigit() and 1 <= int(mfr_choice) <= len(mfrs):
            return mfrs[int(mfr_choice) - 1].pk, False
        elif mfr_choice == "N":
            new_mfr = resolver.create_manufacturer(mfr_input)
            return new_mfr.pk, False
        else:
            return _resolve_manufacturer(resolver, None)
    else:
        if click.confirm(
            f"Manufacturer '{mfr_input}' not found. Create it?", default=True
        ):
            new_mfr = resolver.create_manufacturer(mfr_input)
            return new_mfr.pk, False
    return None, False


def _manual_resolution_loop(unresolved, resolver, supplier_id):
    """Interactive loop for manual part resolution with history and undo."""
    from inventree.company import SupplierPart, ManufacturerPart
    from inventree.part import Part

    i = 0
    history = []

    while i < len(unresolved):
        item = unresolved[i]
        click.secho(
            f"\n--- Manual Resolution ({i + 1}/{len(unresolved)}) ---",
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

        # Use naming convention for the default search query and suggested part name
        suggested_name = NamingConvention.suggest_name(item.api_parameters or {})
        query = suggested_name or item.mpn or item.description

        while not resolved:
            # Auto-search or custom search
            parts = resolver.search_parts(query)
            if parts:
                click.echo("\nSearch Results:")
                for idx, p in enumerate(parts):
                    click.echo(
                        f"  [{idx + 1}] {p.name} (IPN: {getattr(p, 'IPN', '---')}) - {p.description[:50]}"
                    )
                default_choice = "1"
            else:
                click.secho("No matching parts found in InvenTree.", fg="yellow")
                default_choice = "S"

            prompt_text = "\nSelect [1-N], [S]earch, [M]anual PK, [C]reate New, [X]kip"
            if history:
                prompt_text += ", [U]ndo previous"

            choice = click.prompt(prompt_text, type=str, default=default_choice).upper()

            created_info = None
            old_data = {
                "base_part_pk": item.base_part_pk,
                "supplier_part_pk": item.supplier_part_pk,
                "resolution_status": item.resolution_status,
                "part_name": item.part_name,
                "part_description": item.part_description,
                "internal_part_number": item.internal_part_number,
            }

            if choice.isdigit() and 1 <= int(choice) <= len(parts):
                selected_part = parts[int(choice) - 1]
                if click.confirm(
                    f"Permanently link SKU {item.sku} and MPN {item.mpn} to {selected_part.name}?"
                ):
                    default_mfr = (
                        (item.api_parameters or {}).get("Manufacturer")
                        or item.manufacturer
                        or ""
                    )
                    mfr_pk, auto_mfr = _resolve_manufacturer(resolver, default_mfr)
                    created_info = resolver.create_linkage(
                        item, selected_part.pk, supplier_id, mfr_pk
                    )
                else:
                    resolver.link_manual_part(item, selected_part.pk)
                resolved = True
            elif choice == "S":
                query = click.prompt("Enter search term")
            elif choice == "M":
                pk_val = click.prompt("Enter InvenTree Part PK or IPN")
                try:
                    target_pk = None
                    if pk_val.isdigit():
                        target_pk = int(pk_val)
                    else:
                        ipn_parts = resolver.search_parts(pk_val)
                        if ipn_parts and getattr(ipn_parts[0], "IPN", "") == pk_val:
                            target_pk = ipn_parts[0].pk

                    if target_pk:
                        if click.confirm(
                            f"Permanently link SKU {item.sku} to PK {target_pk}?"
                        ):
                            default_mfr = (
                                (item.api_parameters or {}).get("Manufacturer")
                                or item.manufacturer
                                or ""
                            )
                            mfr_pk, auto_mfr = _resolve_manufacturer(
                                resolver, default_mfr
                            )
                            created_info = resolver.create_linkage(
                                item, target_pk, supplier_id, mfr_pk
                            )
                        else:
                            resolver.link_manual_part(item, target_pk)
                        resolved = True
                except Exception as e:
                    click.secho(f"Error: {e}", fg="red")
            elif choice == "C":
                api_params = item.api_parameters or {}
                name = click.prompt(
                    "Part Name",
                    default=suggested_name
                    or api_params.get("MPN")
                    or item.mpn
                    or item.sku,
                )
                desc = click.prompt(
                    "Part Description",
                    default=api_params.get("Description") or item.description,
                )
                cat_pk, auto_cat = _resolve_category(resolver)
                mfr_pk, auto_mfr = _resolve_manufacturer(
                    resolver, api_params.get("Manufacturer") or item.manufacturer or ""
                )
                try:
                    creation_params = NamingConvention.get_category_parameters(
                        api_params
                    )
                    created_info = resolver.create_new_part(
                        item,
                        name,
                        desc,
                        cat_pk,
                        supplier_id,
                        mfr_pk,
                        parameters=creation_params,
                    )
                    resolved = True
                except Exception as e:
                    click.secho(f"Error creating part: {e}", fg="red")
            elif choice == "U" and history:
                # Undo last action
                last = history.pop()
                last_item = last["item"]
                created = last["created"]

                click.echo(f"Undoing resolution for {last_item.sku}...")

                # Deletion from InvenTree
                if created:
                    if "supplier_part" in created:
                        try:
                            SupplierPart(
                                resolver.api, pk=created["supplier_part"]
                            ).delete()
                        except Exception:
                            pass
                    if "manufacturer_part" in created:
                        try:
                            ManufacturerPart(
                                resolver.api, pk=created["manufacturer_part"]
                            ).delete()
                        except Exception:
                            pass
                    if "part" in created:
                        try:
                            Part(resolver.api, pk=created["part"]).delete()
                        except Exception:
                            pass

                # Revert item state
                for key, val in last["old_data"].items():
                    setattr(last_item, key, val)

                i -= 1  # Step back
                resolved = True  # Exit current loop to re-process previous item
                continue
            elif choice == "X":
                resolved = True

        if choice != "U":
            history.append(
                {"item": item, "created": created_info, "old_data": old_data}
            )
            i += 1

    # Final check if last item was auto-selected and no next prompt exists
    # Actually the loop already finished, history has all actions.
    # If the user wants to undo the very last one, they can only do it if we are still in the loop.
    # But wait, if they finish the last item, they might want one last chance to undo.
    if history and click.confirm(
        "\nAll items processed. Undo manufacturer auto-created part?", default=False
    ):
        # We need to run the undo logic one more time.
        # This is slightly redundant but satisfies the "directly offer to undo" for the last item.
        last = history.pop()
        last_item = last["item"]
        created = last["created"]
        click.echo(f"Undoing resolution for {last_item.sku}...")
        if created:
            if "supplier_part" in created:
                try:
                    SupplierPart(resolver.api, pk=created["supplier_part"]).delete()
                except Exception:
                    pass
            if "manufacturer_part" in created:
                try:
                    ManufacturerPart(
                        resolver.api, pk=created["manufacturer_part"]
                    ).delete()
                except Exception:
                    pass
            if "part" in created:
                try:
                    Part(resolver.api, pk=created["part"]).delete()
                except Exception:
                    pass
        for key, val in last["old_data"].items():
            setattr(last_item, key, val)
        # Re-run for the last item
        _manual_resolution_loop([last_item], resolver, supplier_id)


def _run_importer(input_csv, supplier_id, location_id=None, items_list=None, api=None):
    if not api:
        click.echo("Connecting to InvenTree...")
        try:
            api = get_api()
        except Exception as e:
            click.secho(f"Error: Could not connect to InvenTree API: {e}", fg="red")
            return

    # Resolve CSV mapping
    mapping = get_saved_mapping(supplier_id)
    if not mapping:
        click.echo("No saved mapping found for this supplier. Detecting columns...")
        mapping = detect_columns(input_csv)

    # Check for missing required fields
    missing = [f for f in REQUIRED_FIELDS if not mapping.get(f)]
    csv_headers = pd.read_csv(input_csv, nrows=0).columns.tolist()

    def prompt_mapping(current_mapping):
        new_mapping = current_mapping.copy()
        click.echo("\n--- CSV Column Mapping ---")
        table = []
        for field, col in new_mapping.items():
            req = "*" if field in REQUIRED_FIELDS else ""
            table.append([f"{field}{req}", col or click.style("NOT MAPPED", fg="red")])
        click.echo(tabulate(table, headers=["Field", "CSV Column"], tablefmt="simple"))

        if click.confirm("\nEdit this mapping?", default=len(missing) > 0):
            for field in new_mapping.keys():
                req = "*" if field in REQUIRED_FIELDS else ""
                current = new_mapping.get(field)
                click.echo(f"\nTarget Field: {click.style(field + req, bold=True)}")
                click.echo(f"Current Mapping: {current or 'None'}")

                if click.confirm(
                    f"Change mapping for '{field}'?",
                    default=not current and field in REQUIRED_FIELDS,
                ):
                    for idx, h in enumerate(csv_headers):
                        click.echo(f"  [{idx + 1}] {h}")
                    choice = click.prompt(
                        "Select column [1-N] or [0] to leave unmapped",
                        type=int,
                        default=0,
                    )
                    if 0 < choice <= len(csv_headers):
                        new_mapping[field] = csv_headers[choice - 1]
                    else:
                        new_mapping[field] = None
            return new_mapping, True
        return new_mapping, False

    mapping, modified = prompt_mapping(mapping)

    # Final check
    missing = [f for f in REQUIRED_FIELDS if not mapping.get(f)]
    if missing:
        click.secho(
            f"Error: Required fields not mapped: {', '.join(missing)}", fg="red"
        )
        return

    if modified or not get_saved_mapping(supplier_id):
        if click.confirm("Save this mapping for future use?"):
            save_mapping(supplier_id, mapping)

    click.echo(f"Parsing {input_csv}...")
    items = parse_csv(input_csv, mapping)
    click.echo(f"Found {len(items)} items in CSV.")

    click.echo(f"Reconciling items (Supplier ID: {supplier_id})...")
    resolver = Resolver(api)

    with click.progressbar(items, label="Resolving") as bar:
        for item in bar:
            resolver.resolve_item(item, supplier_id)

    # Initial table display
    _print_verification_table(items)

    # Manual fallback for unresolved items
    unresolved = [i for i in items if i.resolution_status in ["Not Found", "Error"]]
    if unresolved and click.confirm(
        f"\nFound {len(unresolved)} unresolved items. Resolve them manually?"
    ):
        _manual_resolution_loop(unresolved, resolver, supplier_id)
        # Re-display table after manual resolution
        resolved_count = _print_verification_table(items)
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


def _select_supplier(api):
    """Interactively select a supplier."""
    from resolver import Resolver

    resolver = Resolver(api)

    while True:
        query = click.prompt("\nSearch for Supplier (name or ID, [X] to abort)")
        if query.upper() == "X":
            raise click.Abort()

        if query.isdigit():
            # Verify ID exists
            try:
                from inventree.company import Company

                supplier = Company(api, pk=int(query))
                if supplier.is_supplier:
                    return supplier.pk
                else:
                    click.secho(f"Company {query} is not a supplier.", fg="yellow")
            except Exception:
                click.secho(f"Supplier ID {query} not found.", fg="red")

        suppliers = resolver.search_suppliers(query)
        if not suppliers:
            click.secho(f"No suppliers found matching '{query}'", fg="yellow")
            continue

        if len(suppliers) == 1:
            click.secho(
                f"Found supplier: {suppliers[0].name} (ID: {suppliers[0].pk})",
                fg="cyan",
            )
            return suppliers[0].pk
        else:
            click.echo("\nMultiple suppliers found:")
            for i, s in enumerate(suppliers):
                desc = getattr(s, "description", "No description")
                click.echo(f"  [{i + 1}] {s.name} (ID: {s.pk}) - {desc[:50]}")

            choice = click.prompt(
                "Select supplier index [1-N], [0] to search again, or [X] to abort",
                default="1",
            ).upper()

            if choice == "X":
                raise click.Abort()
            if choice.isdigit():
                idx = int(choice)
                if 1 <= idx <= len(suppliers):
                    return suppliers[idx - 1].pk


def _select_location(api):
    """Interactively select a stock location."""
    from resolver import Resolver

    resolver = Resolver(api)

    while True:
        query = click.prompt("\nSearch for Stock Location (name or ID, [X] to abort)")
        if query.upper() == "X":
            raise click.Abort()

        if query.isdigit():
            try:
                from inventree.stock import StockLocation

                loc = StockLocation(api, pk=int(query))
                return loc.pk
            except Exception:
                click.secho(f"Location ID {query} not found.", fg="red")

        locations = resolver.search_locations(query)
        if not locations:
            click.secho(f"No locations found matching '{query}'", fg="yellow")
            continue

        if len(locations) == 1:
            click.secho(
                f"Found location: {locations[0].name} (ID: {locations[0].pk})",
                fg="cyan",
            )
            return locations[0].pk
        else:
            click.echo("\nMultiple locations found:")
            for i, loc in enumerate(locations):
                desc = getattr(loc, "description", "No description")
                click.echo(f"  [{i + 1}] {loc.name} (ID: {loc.pk}) - {desc[:50]}")

            choice = click.prompt(
                "Select location index [1-N], [0] to search again, or [X] to abort",
                default="1",
            ).upper()

            if choice == "X":
                raise click.Abort()
            if choice.isdigit():
                idx = int(choice)
                if 1 <= idx <= len(locations):
                    return locations[idx - 1].pk


if __name__ == "__main__":
    cli()
