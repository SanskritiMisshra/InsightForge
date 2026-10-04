"""
Benchmark sample retail e-commerce dataset generator for InsightForge.
Generates realistic multi-month retail transactions with controlled imperfections
to exercise the 10-stage automated analytics pipeline.
"""

import pandas as pd
import numpy as np
import hashlib
from datetime import datetime, timedelta
import random


def generate_benchmark_retail_dataset(n_rows: int = 10000, seed: int = 42) -> pd.DataFrame:
    """
    Generates a deterministic benchmark retail dataset with:
    - 12 months of sales transactions (2025-01-01 to 2025-12-31)
    - Realistic retail product taxonomy (5 categories, 20 SKUs)
    - 4 payment methods (UPI, Credit Card, Net Banking, COD)
    - Controlled quality imperfections (exact duplicates, nulls, whitespace, outliers)
    """
    random.seed(seed)
    np.random.seed(seed)

    start_date = datetime(2025, 1, 1)
    end_date = datetime(2025, 12, 31)
    total_days = (end_date - start_date).days

    categories = {
        "Electronics": [
            ("SKU-EL-001", "UltraHD 4K Smart TV 55-inch", 38999.0),
            ("SKU-EL-002", "Noise-Cancelling Wireless Headphones", 7499.0),
            ("SKU-EL-003", "Pro Mechanical Gaming Keyboard", 4299.0),
            ("SKU-EL-004", "10000mAh Magnetic Power Bank", 1899.0),
            ("SKU-EL-005", "Smart Fitness Tracker Band", 2499.0),
        ],
        "Apparel": [
            ("SKU-AP-001", "Classic Oxford Cotton Shirt", 1499.0),
            ("SKU-AP-002", "Slim-Fit Stretch Denim Jeans", 2199.0),
            ("SKU-AP-003", "All-Weather Windbreaker Jacket", 3499.0),
            ("SKU-AP-004", "Breathable Mesh Athletic Shorts", 899.0),
        ],
        "Home & Kitchen": [
            ("SKU-HK-001", "Cold-Press Slow Masticating Juicer", 5999.0),
            ("SKU-HK-002", "Cast Iron Pre-Seasoned Skillet", 1699.0),
            ("SKU-HK-003", "Microfiber Thermal Queen Bedspread", 2299.0),
            ("SKU-HK-004", "Aroma Ultrasonic Essential Diffuser", 1299.0),
        ],
        "Footwear": [
            ("SKU-FW-001", "Pro Cushion Road Running Shoes", 4599.0),
            ("SKU-FW-002", "Waterproof Vibram Trail Hikers", 6299.0),
            ("SKU-FW-003", "Minimalist Casual Canvas Loafers", 1799.0),
        ],
        "Books & Stationery": [
            ("SKU-BS-001", "Hardcover Bullet Grid Dot Journal", 699.0),
            ("SKU-BS-002", "Architect Precision Fine Liner Set", 849.0),
            ("SKU-BS-003", "Ergonomic Bamboo Desk Organizer", 1199.0),
            ("SKU-BS-004", "The Data-Driven Organization Book", 599.0),
        ],
    }

    flat_products = []
    cat_weights = {
        "Electronics": 0.40,
        "Apparel": 0.25,
        "Home & Kitchen": 0.18,
        "Footwear": 0.12,
        "Books & Stationery": 0.05,
    }

    for cat, items in categories.items():
        w = cat_weights[cat] / len(items)
        for sku, name, price in items:
            flat_products.append((sku, name, cat, price, w))

    skus, names, cats, prices, weights = zip(*flat_products)
    weights = np.array(weights)
    weights /= weights.sum()

    n_customers = 1800
    customer_ids = [f"CUST-{1000 + i}" for i in range(n_customers)]
    customer_weights = np.random.pareto(a=1.5, size=n_customers)
    customer_weights /= customer_weights.sum()

    # Cities and regions
    cities_regions = [
        ("Mumbai", "West"),
        ("Bengaluru", "South"),
        ("Delhi NCR", "North"),
        ("Hyderabad", "South"),
        ("Pune", "West"),
        ("Chennai", "South"),
        ("Kolkata", "East"),
        ("Ahmedabad", "West"),
    ]
    city_weights = [0.25, 0.22, 0.20, 0.12, 0.08, 0.06, 0.04, 0.03]

    payment_methods = ["UPI", "Credit Card", "Net Banking", "Cash on Delivery"]
    payment_weights = [0.48, 0.31, 0.14, 0.07]

    records = []
    base_rows = int(n_rows * 0.988)  # Leave room for duplicate injection

    for i in range(base_rows):
        order_id = f"ORD-2025-{100000 + i}"
        cust_id = np.random.choice(customer_ids, p=customer_weights)

        # Seasonal transaction date generation
        day_offset = random.randint(0, total_days)
        # Add slight Q4 festive boost
        if random.random() < 0.25:
            # bias towards Oct, Nov, Dec (days 273 to 365)
            day_offset = random.randint(270, total_days)

        tx_date = start_date + timedelta(days=day_offset, hours=random.randint(8, 22), minutes=random.randint(0, 59))

        # Select product
        prod_idx = np.random.choice(len(flat_products), p=weights)
        sku, prod_name, cat, unit_price = skus[prod_idx], names[prod_idx], cats[prod_idx], prices[prod_idx]

        # Quantity: mostly 1-3, occasional bulk
        qty = np.random.choice([1, 2, 3, 4, 5, 8], p=[0.70, 0.18, 0.07, 0.03, 0.015, 0.005])

        # Rare high-value outlier for testing outlier detection
        if i == 420 or i == 888:
            qty = 45

        # Discount
        discount_pct = 0.0
        if random.random() < 0.35:
            discount_pct = random.choice([0.05, 0.10, 0.15, 0.20])

        gross_amount = round(qty * unit_price, 2)
        total_amount = round(gross_amount * (1.0 - discount_pct), 2)

        city, region = random.choices(cities_regions, weights=city_weights)[0]
        payment_method = random.choices(payment_methods, weights=payment_weights)[0]

        # Ratings: 1 to 5, with some missingness
        rating = random.choices([5, 4, 3, 2, 1], weights=[0.55, 0.28, 0.10, 0.04, 0.03])[0]
        if random.random() < 0.08:  # 8% missing ratings
            rating = None

        # Subtle whitespace imperfection in category for ~2% rows
        if random.random() < 0.02:
            cat = f" {cat} "

        records.append({
            "order_id": order_id,
            "order_date": tx_date.strftime("%Y-%m-%d %H:%M:%S"),
            "customer_id": cust_id,
            "product_id": sku,
            "product_name": prod_name,
            "category": cat,
            "unit_price": unit_price,
            "quantity": qty,
            "discount_pct": discount_pct,
            "total_amount": total_amount,
            "payment_method": payment_method,
            "city": city,
            "region": region,
            "customer_rating": rating,
        })

    # Inject exact duplicates (~1.2% = 120 rows)
    dupe_count = n_rows - len(records)
    for _ in range(dupe_count):
        dupe_row = random.choice(records[:1000]).copy()
        records.append(dupe_row)

    df = pd.DataFrame(records)
    return df
