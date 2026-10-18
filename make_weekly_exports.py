"""
Creates the weekly export files a food bank worker would pull from their
ordering system (e.g. Agency Express) each Monday. Each file is a full
order-history export as of that Monday — exactly what a real export looks like.

Produces demo_uploads/orders_export_YYYY-MM-DD.csv (+ matching donor pickups),
so the demo replays four consecutive Mondays.
"""
import os
import pandas as pd

os.makedirs("demo_uploads", exist_ok=True)

orders = pd.read_csv("data/orders.csv", parse_dates=["order_date"])
pickups = pd.read_csv("data/pickups.csv", parse_dates=["week_start"])
agencies = pd.read_csv("data/agencies.csv")

MONDAYS = ["2026-06-01", "2026-06-15", "2026-06-29", "2026-07-13"]

for m in MONDAYS:
    cutoff = pd.Timestamp(m)
    o = orders[orders.order_date <= cutoff].merge(
        agencies[["agency_id", "name", "city"]], on="agency_id")
    o = o.rename(columns={"name": "agency_name", "order_date": "order_date",
                          "pounds": "pounds"})[
        ["agency_id", "agency_name", "city", "order_date", "pounds"]]
    o.to_csv(f"demo_uploads/orders_export_{m}.csv", index=False)

    p = pickups[pickups.week_start <= cutoff]
    p.to_csv(f"demo_uploads/pickups_export_{m}.csv", index=False)

print("Created weekly exports for:", ", ".join(MONDAYS))
print("Files in demo_uploads/:", sorted(os.listdir("demo_uploads")))
