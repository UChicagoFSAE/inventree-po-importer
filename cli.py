import click
from tabulate import tabulate
from config import get_api
from parser import parse_csv
from resolver import Resolver

@click.command()
@click.argument('input_csv', type=click.Path(exists=True))
@click.option('--supplier-id', required=True, type=int, help='InvenTree ID for the supplier (e.g. DigiKey)')
def reconcile(input_csv, supplier_id):
    """Reconcile a supplier CSV against InvenTree parts."""
    
    click.echo(f"Connecting to InvenTree...")
    try:
        api = get_api()
    except Exception as e:
        click.secho(f"Error: Could not connect to InvenTree API: {e}", fg='red')
        return

    click.echo(f"Parsing {input_csv}...")
    items = parse_csv(input_csv)
    click.echo(f"Found {len(items)} items in CSV.")

    click.echo(f"Reconciling items (Supplier ID: {supplier_id})...")
    resolver = Resolver(api)
    
    with click.progressbar(items, label='Processing') as bar:
        for item in bar:
            resolver.resolve_item(item, supplier_id)

    # Prepare table data
    table_data = []
    for item in items:
        table_data.append([
            item.index,
            item.sku,
            item.mpn,
            item.base_part_pk if item.base_part_pk else "---",
            item.supplier_part_pk if item.supplier_part_pk else "---",
            item.resolution_status
        ])

    headers = ["#", "SKU", "MPN", "Part PK", "Supp. PK", "Status"]
    click.echo("\nReconciliation Summary:")
    click.echo(tabulate(table_data, headers=headers, tablefmt="grid"))

    # Summary stats
    resolved_count = sum(1 for i in items if "Resolved" in i.resolution_status)
    click.echo(f"\nTotal: {len(items)} | Resolved: {resolved_count} | Failed: {len(items) - resolved_count}")

if __name__ == '__main__':
    reconcile()
