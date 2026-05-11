# AirTrack 1.0.0
# Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC


#
# routes/billing_webhook_routes.py
#
# Stripe Webhook Receiver — Handles completed payments, persists
# customers + licenses + activity, and (optionally) notifies Discord.
#
# NOTE: This blueprint is intended to be registered with:
#     app.register_blueprint(billing_webhook_bp, url_prefix="/billing")
# Which makes the webhook URL:
#     https://billing.airtracksolutions.com/billing/webhook
# matching your Stripe dashboard configuration.

import os
import json
import uuid
from decimal import Decimal

from flask import Blueprint, request, jsonify, current_app
import stripe
from sqlalchemy.exc import SQLAlchemyError

from extensions import db
from models.billing_models import Customer, License, LicenseActivity
from utils.discord_utils import send_sales_notification

# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

billing_webhook_bp = Blueprint("billing_webhook", __name__)

# Stripe secrets
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "").strip()
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()

# Price IDs → human friendly license type
PRICE_STANDARD = os.getenv("STRIPE_PRICE_STANDARD", "").strip() or os.getenv(
    "PRICE_STANDARD", ""
).strip()
PRICE_PRO = os.getenv("STRIPE_PRICE_PRO", "").strip() or os.getenv(
    "PRICE_PRO", ""
).strip()
PRICE_INSTITUTIONAL = os.getenv("STRIPE_PRICE_INSTITUTIONAL", "").strip() or os.getenv(
    "PRICE_INSTITUTIONAL", ""
).strip()

if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY


def determine_license_type(price_id: str) -> str:
    """Map Stripe price IDs to our internal license type labels."""
    if not price_id:
        return "Unknown"

    if price_id == PRICE_STANDARD:
        return "standard"
    if price_id == PRICE_PRO:
        return "professional"
    if price_id == PRICE_INSTITUTIONAL:
        return "institutional"

    return "Unknown"


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------


def _get_invoice_and_price_id(session: dict) -> tuple[str | None, str | None]:
    """
    Best-effort helper to retrieve invoice + price_id for a checkout session.

    - First tries session["invoice"] -> Invoice.retrieve(...).
    - If that fails, falls back to None for price_id.
    """
    invoice_id = session.get("invoice")
    price_id = None

    if not STRIPE_SECRET_KEY:
        # Without secret key we can't call the API — just return IDs we can see
        return invoice_id, price_id

    if not invoice_id:
        return invoice_id, price_id

    try:
        invoice = stripe.Invoice.retrieve(invoice_id)
        lines = invoice.get("lines", {}).get("data", [])
        if lines:
            price = lines[0].get("price") or {}
            price_id = price.get("id")
    except Exception as exc:  # noqa: BLE001
        current_app.logger.warning("Stripe invoice lookup failed: %s", exc)

    return invoice_id, price_id


def _get_or_create_customer(email: str, full_name: str | None) -> Customer:
    """
    Get existing Customer by email, or create a new one.
    Commits only at the outer transaction level.
    """
    customer = Customer.query.filter_by(email=email).first()
    if customer:
        # Optionally refresh name if it was blank and we now have a value
        if full_name and not customer.full_name:
            customer.full_name = full_name
        return customer

    customer = Customer(email=email, full_name=full_name or None)
    db.session.add(customer)
    # Flush so customer.id is populated for the license relationship
    db.session.flush()
    return customer


def _create_license_and_activity(
    customer: Customer,
    license_type: str,
    amount_total: Decimal,
    currency: str,
    session: dict,
    invoice_id: str | None,
) -> License:
    """
    Create a License + initial LicenseActivity entries for this purchase.
    """
    license_key = str(uuid.uuid4())

    license_obj = License(
        license_key=license_key,
        license_type=license_type,
        stripe_session_id=session.get("id"),
        stripe_payment_intent=session.get("payment_intent"),
        purchase_amount=amount_total,
        purchase_currency=currency,
    )
    # Attach to customer via relationship
    customer.licenses.append(license_obj)
    db.session.add(license_obj)
    db.session.flush()

    # Record key events in LicenseActivity
    activities: list[LicenseActivity] = []

    activities.append(
        LicenseActivity(
            license=license_obj,
            event_type="created",
            event_message=f"License created from checkout.session.completed (invoice={invoice_id or 'N/A'})",
        )
    )

    activities.append(
        LicenseActivity(
            license=license_obj,
            event_type="webhook_received",
            event_message="Stripe webhook processed successfully.",
        )
    )

    for act in activities:
        db.session.add(act)

    return license_obj


def _safe_discord_notify(license_type: str, amount: Decimal, currency: str, email: str, invoice_id: str | None, license_key: str) -> None:  # noqa: E501
    """
    Fire-and-forget Discord sales notification.
    Any failure is logged but does not affect webhook success.
    """
    try:
        data = {
            "license_type": license_type,
            "amount": f"{amount:.2f}",
            "currency": currency,
            "customer_email": email,
            "invoice_id": invoice_id or "N/A",
            "license_key": license_key,
        }
        send_sales_notification("checkout.session.completed", data)
    except Exception as exc:  # noqa: BLE001
        # We do NOT want Discord issues to break Stripe webhooks.
        current_app.logger.warning("Discord sales notification failed: %s", exc)

        # Optionally: record an error activity if we have a DB transaction open.
        # We won't here, because it would require passing License in; instead
        # we just log and continue.


# ---------------------------------------------------------------------
# Webhook Route
# ---------------------------------------------------------------------


@billing_webhook_bp.route("/webhook", methods=["POST"])
def stripe_webhook() -> tuple[object, int]:
    """
    Stripe webhook receiver.

    Intended final URL (with blueprint prefix):
        https://billing.airtracksolutions.com/billing/webhook

    Handles:
      - checkout.session.completed
        * Auto-creates Customer if needed (by email).
        * Creates License + LicenseActivity rows.
        * Optionally sends Discord notification.
    """

    # Grab raw payload and signature
    payload = request.data
    sig_header = request.headers.get("Stripe-Signature", "")

    if not STRIPE_WEBHOOK_SECRET:
        current_app.logger.error("STRIPE_WEBHOOK_SECRET not configured.")
        # Still return 200 to avoid endless retries while misconfigured,
        # but log loudly so you can fix it.
        return jsonify({"status": "ignored", "reason": "missing webhook secret"}), 200

    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=sig_header,
            secret=STRIPE_WEBHOOK_SECRET,
        )
    except stripe.error.SignatureVerificationError as exc:
        current_app.logger.warning("Stripe webhook signature verification failed: %s", exc)
        return jsonify({"error": "invalid signature"}), 400
    except ValueError as exc:
        current_app.logger.warning("Stripe webhook invalid payload: %s", exc)
        return jsonify({"error": "invalid payload"}), 400
    except Exception as exc:  # noqa: BLE001
        current_app.logger.error("Stripe webhook error: %s", exc)
        return jsonify({"error": "webhook error"}), 400

    event_type = event.get("type")
    current_app.logger.info("Stripe webhook received: %s", event_type)

    # We care mainly about successful checkout sessions
    if event_type == "checkout.session.completed":
        session = event.get("data", {}).get("object", {}) or {}

        customer_email = (
            session.get("customer_details", {}).get("email")
            or session.get("customer_email")
            or ""
        )
        customer_name = (
            session.get("customer_details", {}).get("name")
            or session.get("client_reference_id")
            or None
        )

        # Stripe gives amounts in cents
        raw_amount = session.get("amount_total") or 0
        try:
            amount_total = Decimal(raw_amount) / Decimal("100")
        except Exception:  # noqa: BLE001
            amount_total = Decimal("0.00")

        currency = (session.get("currency") or "aud").upper()

        invoice_id, price_id = _get_invoice_and_price_id(session)
        license_type = determine_license_type(price_id or "")

        if not customer_email:
            current_app.logger.warning(
                "checkout.session.completed without customer email; session id=%s",
                session.get("id"),
            )
            # We still acknowledge to Stripe to avoid retries;
            # admin can manually fix this case later.
            return jsonify({"status": "ok", "note": "missing customer email"}), 200

        try:
            # Wrap DB writes in a single transaction
            with db.session.begin():
                customer = _get_or_create_customer(customer_email, customer_name)
                license_obj = _create_license_and_activity(
                    customer=customer,
                    license_type=license_type,
                    amount_total=amount_total,
                    currency=currency,
                    session=session,
                    invoice_id=invoice_id,
                )

            # Fire-and-forget Discord (outside the transaction)
            _safe_discord_notify(
                license_type=license_type,
                amount=amount_total,
                currency=currency,
                email=customer_email,
                invoice_id=invoice_id,
                license_key=license_obj.license_key,
            )

        except SQLAlchemyError as exc:
            db.session.rollback()
            current_app.logger.error("DB error in Stripe webhook: %s", exc)
            # Let Stripe retry later; this is a genuine failure
            return jsonify({"error": "database error"}), 500
        except Exception as exc:  # noqa: BLE001
            db.session.rollback()
            current_app.logger.error("Unexpected error in Stripe webhook: %s", exc)
            return jsonify({"error": "unexpected error"}), 500

        return jsonify({"status": "ok"}), 200

    # For all other events, just acknowledge.
    # You can expand this later if you need invoice.paid, etc.
    return jsonify({"status": "ignored", "event_type": event_type}), 200
