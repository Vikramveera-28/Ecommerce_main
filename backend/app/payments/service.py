import uuid
from typing import Optional

from app.extensions import db
from app.models import CustomerPaymentCard, Payment, PaymentMethod, PaymentStatus


def create_cod_payment(order_id: int, amount: float) -> Payment:
    payment = Payment(
        order_id=order_id,
        payment_method=PaymentMethod.COD.value,
        amount=amount,
        payment_status=PaymentStatus.COD_PENDING.value,
    )
    db.session.add(payment)
    db.session.flush()
    return payment


def mark_cod_confirmed(order_id: int) -> Optional[Payment]:
    payment = Payment.query.filter_by(order_id=order_id).first()
    if not payment:
        return None
    payment.payment_status = PaymentStatus.COD_CONFIRMED.value
    return payment


def create_card_payment(order_id: int, amount: float, card_last4: str) -> Payment:
    transaction_id = f"CARD-{order_id:06d}-{uuid.uuid4().hex[:8].upper()}"
    payment = Payment(
        order_id=order_id,
        payment_method=PaymentMethod.CARD.value,
        amount=amount,
        payment_status=PaymentStatus.PAID.value,
        transaction_id=f"{transaction_id}-{card_last4}",
    )
    db.session.add(payment)
    db.session.flush()
    return payment


def verify_customer_card(
    customer_id: int, card_number: str, card_pin: str
) -> Optional[CustomerPaymentCard]:
    profile = CustomerPaymentCard.query.filter_by(customer_id=customer_id).first()
    if not profile:
        return None
    if not profile.check_card_number(card_number):
        return None
    if not profile.check_card_pin(card_pin):
        return None
    return profile
