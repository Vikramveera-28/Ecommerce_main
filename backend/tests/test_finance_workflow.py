from app.extensions import db
from app.models import (
    AccountStatus,
    Address,
    Category,
    Commission,
    CustomerProfile,
    DeliveryProfile,
    LedgerEntry,
    LedgerStatus,
    LogisticsProfile,
    Order,
    OrderItem,
    OrderStatus,
    Payment,
    PaymentMethod,
    PaymentStatus,
    Payout,
    PayoutStatus,
    Product,
    ProductApprovalStatus,
    ProductStatus,
    Role,
    Shipment,
    ShipmentStatus,
    User,
    VendorKycStatus,
    VendorProfile,
)


def _auth_token(client, email, password):
    login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    return login.get_json()["access_token"]


def _create_user(name, email, role, password="pass12345"):
    user = User(name=name, email=email, role=role.value, status=AccountStatus.ACTIVE.value)
    user.set_password(password)
    db.session.add(user)
    db.session.flush()
    return user


def _seed_finance_data(app):
    with app.app_context():
        admin = _create_user("Admin", "admin-finance@test.local", Role.ADMIN)
        customer = _create_user("Buyer", "buyer-finance@test.local", Role.CUSTOMER)
        db.session.add(CustomerProfile(user_id=customer.id))

        vendor_user = _create_user("Vendor Owner", "vendor-finance@test.local", Role.VENDOR)
        vendor = VendorProfile(
            user_id=vendor_user.id,
            store_name="Finance Vendor Store",
            store_slug="finance-vendor-store",
            kyc_status=VendorKycStatus.APPROVED.value,
        )
        db.session.add(vendor)
        db.session.flush()

        logistics_user = _create_user("Logistics Lead", "logistics-finance@test.local", Role.LOGISTICS)
        logistics = LogisticsProfile(user_id=logistics_user.id, service_area="Mumbai", status=AccountStatus.ACTIVE.value)
        db.session.add(logistics)
        db.session.flush()

        delivery_user = _create_user("Rider One", "delivery-finance@test.local", Role.DELIVERY_BOY)
        delivery = DeliveryProfile(user_id=delivery_user.id, phone="9999999999", is_active=True)
        db.session.add(delivery)
        db.session.flush()

        category = Category(name="Fitness", slug="fitness-finance", status=ProductStatus.ACTIVE.value)
        db.session.add(category)
        db.session.flush()

        product = Product(
            vendor_id=vendor.id,
            category_id=category.id,
            name="Finance Test Product",
            sku="FINANCE-SKU-1",
            price=120.0,
            stock_quantity=8,
            status=ProductStatus.ACTIVE.value,
            approval_status=ProductApprovalStatus.APPROVED.value,
        )
        db.session.add(product)
        db.session.flush()

        address = Address(
            user_id=customer.id,
            full_name="Buyer",
            phone="1234567890",
            address_line_1="Street 1",
            city="Mumbai",
            state="MH",
            postal_code="400001",
            country="India",
            is_default=True,
        )
        db.session.add(address)
        db.session.flush()

        order = Order(
            customer_id=customer.id,
            total_amount=120.0,
            payment_status=PaymentStatus.COD_PENDING.value,
            order_status=OrderStatus.PENDING.value,
            shipping_address_id=address.id,
        )
        db.session.add(order)
        db.session.flush()

        order_item = OrderItem(
            order_id=order.id,
            product_id=product.id,
            vendor_id=vendor.id,
            quantity=1,
            price=120.0,
        )
        db.session.add(order_item)
        db.session.flush()

        db.session.add(
            Commission(
                order_item_id=order_item.id,
                vendor_amount=108.0,
                platform_commission=12.0,
                commission_percentage=10.0,
            )
        )
        db.session.add(
            Payment(
                order_id=order.id,
                payment_method=PaymentMethod.COD.value,
                amount=120.0,
                payment_status=PaymentStatus.COD_PENDING.value,
            )
        )
        shipment = Shipment(
            order_id=order.id,
            logistics_id=logistics.id,
            assigned_delivery_boy_id=delivery.id,
            assigned_by_logistics_id=logistics_user.id,
            tracking_number="TRK-FIN-1",
            shipment_status=ShipmentStatus.PICKUP_REQUESTED.value,
            otp_code="123456",
        )
        db.session.add(shipment)
        db.session.commit()

        return {
            "admin_email": admin.email,
            "vendor_email": vendor_user.email,
            "delivery_email": delivery_user.email,
            "logistics_email": logistics_user.email,
            "vendor_profile_id": vendor.id,
            "delivery_profile_id": delivery.id,
            "shipment_id": shipment.id,
            "order_id": order.id,
        }


def _confirm_delivery(client, seeded):
    delivery_token = _auth_token(client, seeded["delivery_email"], "pass12345")
    headers = {"Authorization": f"Bearer {delivery_token}"}

    out_for_delivery = client.patch(
        f"/api/v1/delivery/shipments/{seeded['shipment_id']}/status",
        headers=headers,
        json={"status": "out_for_delivery"},
    )
    assert out_for_delivery.status_code == 200

    confirmed = client.post(
        f"/api/v1/delivery/shipments/{seeded['shipment_id']}/confirm",
        headers=headers,
        json={"otp": "123456"},
    )
    assert confirmed.status_code == 200


def test_delivery_confirmation_creates_ledger_entries_and_self_finance_views(client, app):
    seeded = _seed_finance_data(app)
    _confirm_delivery(client, seeded)

    with app.app_context():
        entries = LedgerEntry.query.order_by(LedgerEntry.actor_type.asc(), LedgerEntry.id.asc()).all()
        assert len(entries) == 4
        by_actor = {(entry.actor_type, entry.entry_code): entry for entry in entries}
        assert by_actor[("delivery_boy", "delivery_completion_fee")].amount == 97.0
        assert by_actor[("delivery_boy", "delivery_completion_fee")].status == LedgerStatus.ELIGIBLE.value
        assert by_actor[("logistics", "logistics_completion_fee")].amount == 30.0
        assert by_actor[("platform", "platform_order_commission")].amount == 12.0
        assert by_actor[("vendor", "vendor_order_earnings")].amount == 108.0

    vendor_token = _auth_token(client, seeded["vendor_email"], "pass12345")
    vendor_headers = {"Authorization": f"Bearer {vendor_token}"}

    summary = client.get("/api/v1/finance/me/summary?range=30d", headers=vendor_headers)
    assert summary.status_code == 200
    summary_payload = summary.get_json()
    assert summary_payload["actor"]["actor_type"] == "vendor"
    assert summary_payload["balances"]["eligible"] == 108.0
    assert summary_payload["period"]["net"] == 108.0

    ledger = client.get("/api/v1/finance/me/ledger?range=30d", headers=vendor_headers)
    assert ledger.status_code == 200
    ledger_payload = ledger.get_json()
    assert len(ledger_payload) == 1
    assert ledger_payload[0]["source_type"] == "order_item"
    assert ledger_payload[0]["source_context"]["order_id"] == seeded["order_id"]


def test_admin_can_create_approve_and_mark_paid_payouts(client, app):
    seeded = _seed_finance_data(app)
    _confirm_delivery(client, seeded)

    admin_token = _auth_token(client, seeded["admin_email"], "pass12345")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    created = client.post(
        "/api/v1/finance/admin/payouts",
        headers=admin_headers,
        json={
            "actor_type": "delivery_boy",
            "actor_id": seeded["delivery_profile_id"],
            "period_start": "2025-01-01",
            "period_end": "2030-01-01",
            "notes": "Weekly rider settlement",
        },
    )
    assert created.status_code == 201
    payout_payload = created.get_json()
    payout_id = payout_payload["id"]
    assert payout_payload["status"] == PayoutStatus.PENDING.value
    assert payout_payload["net_amount"] == 97.0

    approved = client.patch(f"/api/v1/finance/admin/payouts/{payout_id}/approve", headers=admin_headers)
    assert approved.status_code == 200
    assert approved.get_json()["status"] == PayoutStatus.APPROVED.value

    paid = client.patch(
        f"/api/v1/finance/admin/payouts/{payout_id}/mark-paid",
        headers=admin_headers,
        json={"payment_ref": "BANK-REF-1"},
    )
    assert paid.status_code == 200
    assert paid.get_json()["status"] == PayoutStatus.PAID.value
    assert paid.get_json()["payment_ref"] == "BANK-REF-1"

    with app.app_context():
        payout = Payout.query.get(payout_id)
        assert payout is not None
        assert payout.status == PayoutStatus.PAID.value
        delivery_entries = LedgerEntry.query.filter_by(actor_type="delivery_boy").all()
        assert len(delivery_entries) == 1
        assert delivery_entries[0].status == LedgerStatus.SETTLED.value

    delivery_token = _auth_token(client, seeded["delivery_email"], "pass12345")
    delivery_headers = {"Authorization": f"Bearer {delivery_token}"}
    payouts = client.get("/api/v1/finance/me/payouts", headers=delivery_headers)
    assert payouts.status_code == 200
    payouts_payload = payouts.get_json()
    assert len(payouts_payload) == 1
    assert payouts_payload[0]["status"] == PayoutStatus.PAID.value


def test_admin_adjustments_show_up_in_actor_balances(client, app):
    seeded = _seed_finance_data(app)
    _confirm_delivery(client, seeded)

    admin_token = _auth_token(client, seeded["admin_email"], "pass12345")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    adjustment = client.post(
        "/api/v1/finance/admin/adjustments",
        headers=admin_headers,
        json={
            "actor_type": "vendor",
            "actor_id": seeded["vendor_profile_id"],
            "direction": "debit",
            "amount": 15,
            "description": "Return reserve",
        },
    )
    assert adjustment.status_code == 201
    adjustment_payload = adjustment.get_json()
    assert adjustment_payload["direction"] == "debit"
    assert adjustment_payload["amount"] == 15.0

    adjustments = client.get(
        f"/api/v1/finance/admin/adjustments?role=vendor&actor_id={seeded['vendor_profile_id']}",
        headers=admin_headers,
    )
    assert adjustments.status_code == 200
    adjustments_payload = adjustments.get_json()
    assert len(adjustments_payload) == 1
    assert adjustments_payload[0]["description"] == "Return reserve"

    actors = client.get("/api/v1/finance/admin/actors?role=vendor", headers=admin_headers)
    assert actors.status_code == 200
    actors_payload = actors.get_json()
    assert len(actors_payload) == 1
    assert actors_payload[0]["balances"]["eligible"] == 93.0
