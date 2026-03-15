from app.extensions import db
from app.models import (
    AccountStatus,
    Address,
    Category,
    CustomerProfile,
    DeliveryProfile,
    LogisticsProfile,
    Order,
    OrderItem,
    OrderStatus,
    Payment,
    PaymentMethod,
    PaymentStatus,
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


def _create_user(name, email, role, password):
    user = User(name=name, email=email, role=role.value, status=AccountStatus.ACTIVE.value)
    user.set_password(password)
    db.session.add(user)
    db.session.flush()
    return user


def _seed_workflow_data(app):
    with app.app_context():
        customer = _create_user("Buyer", "buyer-workflow@test.local", Role.CUSTOMER, "pass12345")
        db.session.add(CustomerProfile(user_id=customer.id))

        vendor_user = _create_user("Vendor", "vendor-workflow@test.local", Role.VENDOR, "pass12345")
        vendor = VendorProfile(
            user_id=vendor_user.id,
            store_name="Vendor Workflow Store",
            store_slug="vendor-workflow-store",
            kyc_status=VendorKycStatus.APPROVED.value,
        )
        db.session.add(vendor)
        db.session.flush()

        logistics_user = _create_user("Logistics", "logistics-workflow@test.local", Role.LOGISTICS, "pass12345")
        logistics = LogisticsProfile(user_id=logistics_user.id, status=AccountStatus.ACTIVE.value)
        db.session.add(logistics)
        db.session.flush()

        delivery_user = _create_user("Rider", "delivery-workflow@test.local", Role.DELIVERY_BOY, "pass12345")
        delivery = DeliveryProfile(user_id=delivery_user.id, phone="9999999999", is_active=True)
        db.session.add(delivery)
        db.session.flush()

        category = Category(name="Electronics", slug="electronics-workflow", status=ProductStatus.ACTIVE.value)
        db.session.add(category)
        db.session.flush()

        product = Product(
            vendor_id=vendor.id,
            category_id=category.id,
            name="Workflow Product",
            sku="WORKFLOW-SKU",
            price=120.0,
            stock_quantity=10,
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

        db.session.add(
            OrderItem(
                order_id=order.id,
                product_id=product.id,
                vendor_id=vendor.id,
                quantity=1,
                price=120.0,
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
        db.session.add(
            Shipment(
                order_id=order.id,
                logistics_id=logistics.id,
                assigned_delivery_boy_id=delivery.id,
                assigned_by_logistics_id=logistics_user.id,
                tracking_number="TRK-WORKFLOW-1",
                shipment_status=ShipmentStatus.PICKUP_REQUESTED.value,
                otp_code="123456",
            )
        )
        db.session.commit()

        shipment = Shipment.query.filter_by(order_id=order.id).first()
        return {
            "order_id": order.id,
            "shipment_id": shipment.id,
            "vendor_email": vendor_user.email,
            "logistics_email": logistics_user.email,
            "delivery_email": delivery_user.email,
        }


def test_vendor_cannot_set_delivered_and_follows_preparation_transitions(client, app):
    seeded = _seed_workflow_data(app)
    vendor_token = _auth_token(client, seeded["vendor_email"], "pass12345")
    headers = {"Authorization": f"Bearer {vendor_token}"}

    for status in ["confirmed", "packed", "shipped"]:
        response = client.patch(f"/api/v1/vendor/orders/{seeded['order_id']}/status", headers=headers, json={"status": status})
        assert response.status_code == 200
        assert response.get_json()["order_status"] == status

    delivered_attempt = client.patch(
        f"/api/v1/vendor/orders/{seeded['order_id']}/status",
        headers=headers,
        json={"status": "delivered"},
    )
    assert delivered_attempt.status_code == 400

    with app.app_context():
        order = Order.query.get(seeded["order_id"])
        assert order.order_status == OrderStatus.SHIPPED.value
        assert order.payment_status == PaymentStatus.COD_PENDING.value


def test_logistics_cannot_mark_delivered(client, app):
    seeded = _seed_workflow_data(app)
    logistics_token = _auth_token(client, seeded["logistics_email"], "pass12345")
    headers = {"Authorization": f"Bearer {logistics_token}"}

    picked = client.patch(
        f"/api/v1/logistics/shipments/{seeded['shipment_id']}/status",
        headers=headers,
        json={"status": "picked"},
    )
    assert picked.status_code == 200
    assert picked.get_json()["shipment_status"] == "picked"

    with app.app_context():
        order = Order.query.get(seeded["order_id"])
        assert order.order_status == OrderStatus.SHIPPED.value

    delivered_attempt = client.patch(
        f"/api/v1/logistics/shipments/{seeded['shipment_id']}/status",
        headers=headers,
        json={"status": "delivered", "otp": "123456"},
    )
    assert delivered_attempt.status_code == 400
    assert "delivery boy" in delivered_attempt.get_json()["error"].lower()

    with app.app_context():
        shipment = Shipment.query.get(seeded["shipment_id"])
        assert shipment.shipment_status == ShipmentStatus.PICKED.value


def test_delivery_confirm_is_only_delivered_path_and_confirms_cod(client, app):
    seeded = _seed_workflow_data(app)
    delivery_token = _auth_token(client, seeded["delivery_email"], "pass12345")
    headers = {"Authorization": f"Bearer {delivery_token}"}

    direct_delivered_attempt = client.patch(
        f"/api/v1/delivery/shipments/{seeded['shipment_id']}/status",
        headers=headers,
        json={"status": "delivered"},
    )
    assert direct_delivered_attempt.status_code == 400
    assert "confirm" in direct_delivered_attempt.get_json()["error"].lower()

    set_out_for_delivery = client.patch(
        f"/api/v1/delivery/shipments/{seeded['shipment_id']}/status",
        headers=headers,
        json={"status": "out_for_delivery"},
    )
    assert set_out_for_delivery.status_code == 200
    assert set_out_for_delivery.get_json()["shipment_status"] == ShipmentStatus.OUT_FOR_DELIVERY.value

    wrong_otp = client.post(
        f"/api/v1/delivery/shipments/{seeded['shipment_id']}/confirm",
        headers=headers,
        json={"otp": "000000"},
    )
    assert wrong_otp.status_code == 400

    with app.app_context():
        shipment = Shipment.query.get(seeded["shipment_id"])
        order = Order.query.get(seeded["order_id"])
        assert shipment.shipment_status == ShipmentStatus.OUT_FOR_DELIVERY.value
        assert shipment.delivery_attempts == 1
        assert order.order_status == OrderStatus.SHIPPED.value
        assert order.payment_status == PaymentStatus.COD_PENDING.value

    confirmed = client.post(
        f"/api/v1/delivery/shipments/{seeded['shipment_id']}/confirm",
        headers=headers,
        json={"otp": "123456"},
    )
    assert confirmed.status_code == 200
    assert confirmed.get_json()["shipment_status"] == ShipmentStatus.DELIVERED.value

    with app.app_context():
        shipment = Shipment.query.get(seeded["shipment_id"])
        order = Order.query.get(seeded["order_id"])
        payment = Payment.query.filter_by(order_id=seeded["order_id"]).first()
        assert shipment.shipment_status == ShipmentStatus.DELIVERED.value
        assert order.order_status == OrderStatus.DELIVERED.value
        assert order.payment_status == PaymentStatus.COD_CONFIRMED.value
        assert payment is not None
        assert payment.payment_status == PaymentStatus.COD_CONFIRMED.value
