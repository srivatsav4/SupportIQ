"""Deterministic synthetic data generator for the fictional company NovaCart Technologies.

ALL data produced here is fake and created solely for demonstration/testing.
Same seed => same database.
"""
import random
from datetime import datetime, timedelta

FIRST = ["Aarav", "Priya", "Rohan", "Ananya", "Vikram", "Sneha", "Karthik", "Meera", "Arjun", "Divya", "Rahul",
         "Neha", "Sanjay", "Pooja", "Amit", "Kavya", "Ishaan", "Lakshmi", "Rajesh", "Tara", "Emma", "Liam",
         "Olivia", "Noah", "Sophia", "Mason", "Ava", "Lucas", "Mia", "Ethan"]
LAST = ["Sharma", "Reddy", "Patel", "Iyer", "Nair", "Gupta", "Singh", "Kumar", "Das", "Rao", "Mehta", "Joshi",
        "Verma", "Menon", "Naidu", "Smith", "Johnson", "Brown", "Davis", "Wilson", "Clark", "Lewis", "Walker",
        "Hall", "Young"]
CITIES = ["Bengaluru", "Hyderabad", "Chennai", "Mumbai", "Pune", "Delhi", "Kochi", "Ahmedabad", "Austin",
          "Denver", "Seattle", "Boston"]
STREETS = ["MG Road", "Park Street", "Lake View Road", "Gandhi Nagar", "Maple Avenue", "Cedar Lane",
           "Sunrise Colony", "Hill Road"]
# category -> (product names, (min price, max price), warranty months)
CATS = {
    "Electronics": (["Wireless Earbuds", "Bluetooth Speaker", "Smartwatch", "Laptop Stand", "USB-C Hub",
                     "Power Bank", "Mechanical Keyboard", "Webcam", "Tablet", "Noise Cancelling Headphones"],
                    (25, 650), 12),
    "Home Appliances": (["Air Fryer", "Mixer Grinder", "Robot Vacuum", "Electric Kettle", "Air Purifier",
                         "Induction Cooktop", "Toaster Oven", "Water Heater"], (30, 420), 24),
    "Accessories": (["Phone Case", "Screen Guard", "Charging Cable", "Laptop Sleeve", "Wall Charger",
                     "Car Mount"], (5, 45), 6),
    "Furniture": (["Office Chair", "Standing Desk", "Bookshelf", "Bedside Table", "Shoe Rack"], (60, 520), 12),
    "Clothing": (["Running Shoes", "Cotton T-Shirt", "Denim Jacket", "Hoodie", "Backpack"], (12, 110), 0),
    "Personal Care": (["Trimmer", "Hair Dryer", "Electric Toothbrush", "Face Serum"], (10, 90), 0),
}
CARRIERS = ["SwiftShip", "BlueLine Logistics", "RapidPost"]
CARRIER_PREFIX = {"SwiftShip": "SS", "BlueLine Logistics": "BL", "RapidPost": "RP"}
REFUND_REASONS = ["Item damaged on arrival", "Change of mind", "Wrong product received"]
PAY = ["Credit Card", "Debit Card", "UPI", "Net Banking", "NovaWallet"]
SUFFIX = ["Pro", "Lite", "Max", "Plus", "S"]
BRANDS = ["Nova", "Zephyr", "Orbit", "Pixel", "Lumen", "Vertex", "Aero"]


def generate(seed=42, n_customers=1000, n_products=120, n_orders=2200, as_of=datetime(2026, 9, 30)):
    r = random.Random(seed)
    D = {k: [] for k in ["customers", "products", "orders", "order_items", "payments", "refunds",
                         "shipments", "tickets"]}

    def addr():
        return f"{r.randint(1, 220)}, {r.choice(STREETS)}, {r.choice(CITIES)}"

    # ---------------- customers ----------------
    for i in range(n_customers):
        fn, ln = r.choice(FIRST), r.choice(LAST)
        D["customers"].append(dict(
            customer_id=f"C{1001 + i}", name=f"{fn} {ln}", email=f"{fn}.{ln}{1001 + i}@example.com".lower(),
            phone=f"+91-9{r.randint(100000000, 999999999)}",
            membership_tier=r.choices(["Silver", "Gold", "Platinum"], [0.7, 0.22, 0.08])[0], role="CUSTOMER",
            created_at=(as_of - timedelta(days=r.randint(30, 1200))).isoformat()))
    D["customers"].append(dict(customer_id="S9001", name="Maya Support", email="agent@novacart.example",
                               phone="+91-9000000001", membership_tier="Platinum", role="SUPPORT_AGENT",
                               created_at=as_of.isoformat()))
    D["customers"].append(dict(customer_id="S9002", name="Admin Nova", email="admin@novacart.example",
                               phone="+91-9000000002", membership_tier="Platinum", role="ADMIN",
                               created_at=as_of.isoformat()))

    # ---------------- products ----------------
    pid = 1
    while len(D["products"]) < n_products:
        for cat, (names, (lo, hi), warranty) in CATS.items():
            for nm in names:
                if len(D["products"]) >= n_products:
                    break
                brand = r.choice(BRANDS)
                D["products"].append(dict(
                    product_id=f"P{1000 + pid}", name=f"{brand} {nm} {r.choice(SUFFIX)}", category=cat,
                    price=round(r.uniform(lo, hi), 2), inventory=r.choice([0, 3, 8, 25, 60, 150]),
                    description=f"{nm} from {brand} with manufacturer support. Category: {cat}.",
                    warranty_period=warranty))
                pid += 1
    plist = D["products"]
    cust = [c for c in D["customers"] if c["role"] == "CUSTOMER"]
    cnt = dict(o=10001, oi=1, pay=1, ref=1, sh=1, tk=1)

    def add_order(customer, status, age, delivered_days_ago=None, expected_offset=None, items=None, oid=None,
                  pay_status="Success", pay_count=1, forced_total=None):
        if oid is None:
            oid = f"A{cnt['o']}"
            cnt["o"] += 1
        od = as_of - timedelta(days=age)
        items = items or [(r.choice(plist), r.randint(1, 3)) for _ in range(r.choice([1, 1, 2, 3]))]
        subtotal = sum(p["price"] * q for p, q in items)
        total = forced_total if forced_total is not None else round(subtotal + (0 if subtotal >= 50 else 4.99), 2)
        exp = od + timedelta(days=r.randint(3, 7)) if expected_offset is None else as_of + timedelta(days=expected_offset)
        delivered_at = (as_of - timedelta(days=delivered_days_ago)) if delivered_days_ago is not None else None
        D["orders"].append(dict(
            order_id=oid, customer_id=customer["customer_id"], order_date=od.isoformat(), status=status,
            total_amount=total, shipping_address=addr(), expected_delivery=exp.isoformat(),
            delivered_at=delivered_at.isoformat() if delivered_at else None))
        for p, q in items:
            D["order_items"].append(dict(order_item_id=f"OI{cnt['oi']}", order_id=oid, product_id=p["product_id"],
                                         quantity=q, price=p["price"]))
            cnt["oi"] += 1
        method = r.choice(PAY)
        last4 = f"{r.randint(0, 9999):04d}" if "Card" in method else None
        ref = f"TXN-{r.randint(10 ** 9, 10 ** 10 - 1)}"
        for k in range(pay_count):
            D["payments"].append(dict(
                payment_id=f"PAY{cnt['pay']}", order_id=oid, payment_method=method, card_last4=last4, amount=total,
                status=pay_status, transaction_reference=ref if k == 0 else f"TXN-{r.randint(10 ** 9, 10 ** 10 - 1)}",
                created_at=(od + timedelta(minutes=k * 2)).isoformat()))
            cnt["pay"] += 1
        if status in ("Shipped", "Out for Delivery", "Delivered", "Returned"):
            sstat = {"Shipped": "In Transit", "Out for Delivery": "Out for Delivery", "Delivered": "Delivered",
                     "Returned": "Delivered"}[status]
            last_update = delivered_at if delivered_at else as_of - timedelta(hours=r.randint(2, 40))
            carrier = r.choice(CARRIERS)
            D["shipments"].append(dict(
                shipment_id=f"SH{cnt['sh']}", order_id=oid, carrier=carrier,
                tracking_number=f"{CARRIER_PREFIX[carrier]}{r.randint(10 ** 9, 10 ** 10 - 1)}", status=sstat,
                expected_delivery=exp.isoformat(), last_update=last_update.isoformat()))
            cnt["sh"] += 1
        return oid

    def add_refund(oid, amount, reason, status, days_ago):
        ini = as_of - timedelta(days=days_ago)
        D["refunds"].append(dict(
            refund_id=f"R{cnt['ref']}", order_id=oid, amount=amount, reason=reason, status=status,
            initiated_at=ini.isoformat(),
            completed_at=(ini + timedelta(days=6)).isoformat() if status == "Completed" else None))
        cnt["ref"] += 1

    def add_ticket(customer, category, priority, status, desc, oid=None, days_ago=1):
        D["tickets"].append(dict(
            ticket_id=f"TK{cnt['tk']:05d}", customer_id=customer["customer_id"], category=category,
            priority=priority, status=status, description=desc,
            assigned_agent=r.choice(["Maya Support", None]), order_id=oid,
            created_at=(as_of - timedelta(days=days_ago)).isoformat()))
        cnt["tk"] += 1

    # ---------------- bulk orders with a realistic status mix ----------------
    statuses = ["Delivered", "Shipped", "Out for Delivery", "Processing", "Confirmed", "Pending", "Cancelled", "Returned"]
    weights = [0.55, 0.11, 0.04, 0.07, 0.05, 0.03, 0.09, 0.06]
    for _ in range(n_orders):
        c = r.choice(cust)
        status = r.choices(statuses, weights)[0]
        if status == "Delivered":
            age = r.randint(4, 200)
            oid = add_order(c, status, age, delivered_days_ago=max(age - r.randint(3, 7), 1))
        elif status == "Returned":
            age = r.randint(20, 90)
            oid = add_order(c, status, age, delivered_days_ago=age - 5)
            add_refund(oid, D["orders"][-1]["total_amount"], "Change of mind", "Completed", max(age - 15, 1))
        elif status == "Shipped":
            oid = add_order(c, status, r.randint(2, 12), expected_offset=r.choice([-6, -3, -2, -1, 0, 1, 2, 3, 4]))
        elif status == "Out for Delivery":
            oid = add_order(c, status, r.randint(2, 8), expected_offset=r.choice([0, 1]))
        elif status == "Cancelled":
            age = r.randint(3, 100)
            oid = add_order(c, status, age, pay_status="Refunded")
            add_refund(oid, D["orders"][-1]["total_amount"], "Order cancelled before shipment", "Completed", max(age - 1, 1))
        elif status == "Pending":
            oid = add_order(c, status, r.randint(0, 1), pay_status=r.choice(["Pending", "Failed", "Success"]))
        else:
            oid = add_order(c, status, r.randint(0, 3))
        roll = r.random()
        if roll < 0.02 and status in ("Delivered", "Processing", "Confirmed"):      # duplicate payment edge case
            dup = dict(D["payments"][-1])
            dup["payment_id"] = f"PAY{cnt['pay']}"
            cnt["pay"] += 1
            D["payments"].append(dup)
        if roll > 0.985 and status == "Shipped":                                     # carrier exception edge case
            D["shipments"][-1]["status"] = "Exception"
        if 0.90 < roll < 0.93 and status == "Delivered":
            add_refund(oid, D["orders"][-1]["total_amount"], r.choice(REFUND_REASONS),
                       r.choice(["Initiated", "Approved", "Completed", "Rejected"]), r.randint(1, 20))
        if 0.95 < roll < 0.975:
            add_ticket(c, r.choice(["Delivery", "Refund", "Payment", "Damaged Product", "Account", "General"]),
                       r.choice(["Low", "Medium", "High"]), r.choice(["Open", "In Progress", "Resolved", "Closed"]),
                       "Customer reported an issue (synthetic ticket).", oid, r.randint(1, 60))

    # ---------------- DEMO SCENARIOS (fixed ids, work right after setup) ----------------
    cheap = [p for p in plist if 20 < p["price"] < 120 and p["category"] != "Personal Care"]
    c1, c2, c3 = D["customers"][0], D["customers"][1], D["customers"][2]
    c1.update(name="Priya Sharma", email="priya.sharma@example.com", membership_tier="Silver")   # C1001
    c2.update(name="Rohan Mehta", email="rohan.mehta@example.com", membership_tier="Gold")        # C1002
    c3.update(name="Ananya Iyer", email="ananya.iyer@example.com", membership_tier="Platinum")    # C1003
    add_order(c1, "Shipped", 8, expected_offset=2, oid="A12346", items=[(plist[0], 1)])            # 1 tracking, on time
    add_order(c1, "Shipped", 9, expected_offset=-2, oid="A12345", items=[(plist[1], 1)])           # 2 delayed 2 days
    add_order(c1, "Delivered", 20, delivered_days_ago=14, oid="A12347", items=[(cheap[0], 1)])     # 3 refund status
    add_refund("A12347", D["orders"][-1]["total_amount"], "Change of mind", "Approved", 3)
    add_order(c1, "Delivered", 16, delivered_days_ago=10, oid="A12348", items=[(cheap[1], 1)])     # 4 return eligible
    add_order(c1, "Delivered", 50, delivered_days_ago=40, oid="A12349", items=[(cheap[2], 1)])     # 4 return NOT eligible
    add_order(c1, "Shipped", 17, expected_offset=-8, oid="A12350", items=[(plist[6], 1)])          # severe delay
    add_order(c1, "Delivered", 8, delivered_days_ago=2, oid="A12351", items=[(cheap[3], 1)])       # 5 damaged product
    add_order(c1, "Delivered", 7, delivered_days_ago=2, oid="A12352", items=[(plist[8], 1)], pay_count=2)  # 6 duplicate payment
    hv = [p for p in plist if p["category"] == "Electronics" and p["price"] > 300][0]
    add_order(c1, "Delivered", 9, delivered_days_ago=3, oid="A12353", items=[(hv, 2)])             # 10 high-value refund
    add_order(c1, "Processing", 1, oid="A12354", items=[(plist[9], 1)])                            # cancellable order
    add_order(c2, "Shipped", 6, expected_offset=1, oid="A20001", items=[(plist[3], 1)])            # 9 belongs to another customer
    add_order(c3, "Delivered", 40, delivered_days_ago=35, oid="A30001", items=[(plist[10], 1)])    # Platinum, still in 60-day window
    add_ticket(c1, "Refund", "Medium", "In Progress", "Refund for A12347 is being processed.", "A12347", 3)
    return D
