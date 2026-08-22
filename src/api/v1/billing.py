"""
MODULE 6 ROUTER: Billing & Finance

Real-world business rules enforced here:
    - Invoice totals are always SERVER-COMPUTED from items (quantity * unit_price),
      never trusted from the client — this prevents a tampered request from
      billing the wrong amount.
    - An invoice's patient_id must match the patient on its linked
      admission/appointment (if any) — prevents billing the wrong patient.
    - Finalized invoices (paid/cancelled) cannot have items added.
    - Payments cannot exceed the remaining balance (no overpayment).
    - Invoice status auto-transitions: unpaid -> partially_paid -> paid,
      driven entirely by the running total of payments.
    - Billing data is financial/sensitive: scoped so a patient sees only
      their own invoices; broader access requires a billing permission.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.core.clinical_access import get_own_patient_record
from src.core.database import get_db
from src.core.dependencies import RequirePermission, get_current_user
from src.models.billing import Invoice, InvoiceItem, InvoiceStatusEnum, InsuranceProvider, PatientInsurance, Payment
from src.models.clinical import Admission, Appointment
from src.models.IAM import User
from src.models.profile import PatientDetails
from src.schemas.billing import (
    InsuranceProviderCreate,
    InsuranceProviderResponse,
    InvoiceCreate,
    InvoiceItemCreate,
    InvoiceItemResponse,
    InvoiceResponse,
    PatientInsuranceCreate,
    PatientInsuranceResponse,
    PaymentCreate,
    PaymentResponse,
)

router = APIRouter(tags=["Billing & Finance"])


def _assert_billing_access(db: Session, current_user: User, patient_id: int) -> None:
    """Financial records: visible to the patient themself, or staff holding a billing permission."""
    if current_user.is_superuser:
        return
    granted = {p.code for r in current_user.roles for p in r.permissions}
    if "billing:manage_invoices" in granted or "billing:view_invoices" in granted:
        return
    own_patient = get_own_patient_record(db, current_user)
    if own_patient is not None and own_patient.id == patient_id:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You do not have access to this patient's billing records.",
    )


def _recompute_invoice_status(invoice: Invoice) -> None:
    """Derives invoice.status purely from paid_amount vs total_amount."""
    if invoice.status == InvoiceStatusEnum.CANCELLED:
        return
    if invoice.paid_amount <= 0:
        invoice.status = InvoiceStatusEnum.UNPAID
    elif invoice.paid_amount < invoice.total_amount:
        invoice.status = InvoiceStatusEnum.PARTIALLY_PAID
    else:
        invoice.status = InvoiceStatusEnum.PAID


# =========================================================================
# INVOICES
# =========================================================================
@router.post(
    "/invoices",
    response_model=InvoiceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an itemized invoice",
    description=(
        "total_amount is always computed server-side from the items (quantity * unit_price) — "
        "the client cannot set it directly. Requires at least one item."
    ),
    dependencies=[Depends(RequirePermission("billing:manage_invoices"))],
    responses={
        400: {"description": "No items provided, or patient_id doesn't match the linked admission/appointment"},
        404: {"description": "Patient, admission, or appointment not found"},
    },
)
def create_invoice(payload: InvoiceCreate, db: Session = Depends(get_db)) -> Invoice:
    if db.get(PatientDetails, payload.patient_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    if not payload.items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="An invoice must have at least one item")

    if payload.admission_id is not None:
        admission = db.get(Admission, payload.admission_id)
        if admission is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admission not found")
        if admission.patient_id != payload.patient_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="patient_id does not match the admission's patient")

    if payload.appointment_id is not None:
        appointment = db.get(Appointment, payload.appointment_id)
        if appointment is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")
        if appointment.patient_id != payload.patient_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="patient_id does not match the appointment's patient")

    invoice = Invoice(
        patient_id=payload.patient_id,
        admission_id=payload.admission_id,
        appointment_id=payload.appointment_id,
        total_amount=0,
        paid_amount=0,
        status=InvoiceStatusEnum.UNPAID,
    )
    db.add(invoice)
    db.flush()

    total = 0.0
    for item in payload.items:
        amount = round(item.quantity * item.unit_price, 2)
        total += amount
        db.add(InvoiceItem(
            invoice_id=invoice.id, item_type=item.item_type, description=item.description,
            quantity=item.quantity, unit_price=item.unit_price, amount=amount,
        ))

    invoice.total_amount = round(total, 2)
    db.commit()
    db.refresh(invoice)
    return invoice


@router.get(
    "/invoices",
    response_model=list[InvoiceResponse],
    summary="List invoices",
    description="Patients see only their own invoices; billing staff (with billing:view_invoices or manage) see all.",
)
def list_invoices(
    patient_id: int | None = Query(default=None),
    invoice_status: InvoiceStatusEnum | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Invoice]:
    query = db.query(Invoice)
    granted = {p.code for r in current_user.roles for p in r.permissions}
    has_broad_access = current_user.is_superuser or "billing:view_invoices" in granted or "billing:manage_invoices" in granted

    if not has_broad_access:
        own_patient = get_own_patient_record(db, current_user)
        if own_patient is None:
            return []
        query = query.filter(Invoice.patient_id == own_patient.id)

    if patient_id is not None:
        query = query.filter(Invoice.patient_id == patient_id)
    if invoice_status is not None:
        query = query.filter(Invoice.status == invoice_status)
    return query.all()


@router.get(
    "/invoices/{invoice_id}",
    response_model=InvoiceResponse,
    summary="Get an invoice with its items",
    responses={403: {"description": "Not this invoice's patient or billing staff"}, 404: {"description": "Invoice not found"}},
)
def get_invoice(invoice_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> Invoice:
    invoice = db.get(Invoice, invoice_id)
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    _assert_billing_access(db, current_user, invoice.patient_id)
    return invoice


@router.post(
    "/invoices/{invoice_id}/items",
    response_model=InvoiceItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a line item to an existing invoice",
    description="Recomputes total_amount. Blocked once the invoice is paid or cancelled.",
    dependencies=[Depends(RequirePermission("billing:manage_invoices"))],
    responses={400: {"description": "Invoice is already paid/cancelled"}, 404: {"description": "Invoice not found"}},
)
def add_invoice_item(invoice_id: int, payload: InvoiceItemCreate, db: Session = Depends(get_db)) -> InvoiceItem:
    invoice = db.get(Invoice, invoice_id)
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    if invoice.status in (InvoiceStatusEnum.PAID, InvoiceStatusEnum.CANCELLED):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Cannot modify an invoice that is already '{invoice.status.value}'")

    amount = round(payload.quantity * payload.unit_price, 2)
    item = InvoiceItem(
        invoice_id=invoice_id, item_type=payload.item_type, description=payload.description,
        quantity=payload.quantity, unit_price=payload.unit_price, amount=amount,
    )
    db.add(item)
    # invoice.total_amount comes back from the DB as a Decimal (Numeric column) once
    # persisted — convert to float before mixing with the plain-float `amount` here.
    invoice.total_amount = round(float(invoice.total_amount) + amount, 2)
    _recompute_invoice_status(invoice)
    db.commit()
    db.refresh(item)
    return item


# =========================================================================
# PAYMENTS
# =========================================================================
@router.post(
    "/payments",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record a payment against an invoice",
    description="Rejected if it would exceed the invoice's remaining balance (no overpayment).",
    dependencies=[Depends(RequirePermission("billing:manage_invoices"))],
    responses={
        400: {"description": "Payment exceeds remaining balance, or invoice is already paid/cancelled"},
        404: {"description": "Invoice not found"},
    },
)
def record_payment(
    payload: PaymentCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> Payment:
    invoice = db.get(Invoice, payload.invoice_id)
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    if invoice.status in (InvoiceStatusEnum.PAID, InvoiceStatusEnum.CANCELLED):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invoice is already '{invoice.status.value}'")

    # invoice.total_amount / paid_amount come back from the DB as Decimal
    # (Numeric columns) — convert to float before arithmetic with the
    # plain-float payload.amount_paid, to avoid a Decimal+float TypeError.
    remaining = round(float(invoice.total_amount) - float(invoice.paid_amount), 2)
    if payload.amount_paid > remaining:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Payment of {payload.amount_paid} exceeds remaining balance of {remaining}",
        )

    payment = Payment(
        invoice_id=payload.invoice_id, amount_paid=payload.amount_paid, payment_method=payload.payment_method,
        transaction_date=payload.transaction_date, processed_by=current_user.id,
    )
    db.add(payment)
    invoice.paid_amount = round(float(invoice.paid_amount) + payload.amount_paid, 2)
    _recompute_invoice_status(invoice)
    db.commit()
    db.refresh(payment)
    return payment


@router.get(
    "/invoices/{invoice_id}/payments",
    response_model=list[PaymentResponse],
    summary="List payments made against an invoice",
    responses={403: {"description": "Not this invoice's patient or billing staff"}, 404: {"description": "Invoice not found"}},
)
def list_invoice_payments(
    invoice_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> list[Payment]:
    invoice = db.get(Invoice, invoice_id)
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    _assert_billing_access(db, current_user, invoice.patient_id)
    return db.query(Payment).filter(Payment.invoice_id == invoice_id).all()


# =========================================================================
# INSURANCE
# =========================================================================
@router.post(
    "/insurance-providers",
    response_model=InsuranceProviderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add an insurance provider",
    dependencies=[Depends(RequirePermission("billing:manage_insurance"))],
    responses={400: {"description": "Provider name already exists"}},
)
def create_insurance_provider(payload: InsuranceProviderCreate, db: Session = Depends(get_db)) -> InsuranceProvider:
    if db.query(InsuranceProvider).filter(InsuranceProvider.name == payload.name).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This insurance provider already exists")
    provider = InsuranceProvider(**payload.model_dump())
    db.add(provider)
    db.commit()
    db.refresh(provider)
    return provider
    

@router.get(
    "/insurance-providers",
    response_model=list[InsuranceProviderResponse],
    summary="List insurance providers",
)
def list_insurance_providers(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[InsuranceProvider]:
    return db.query(InsuranceProvider).all()


@router.post(
    "/patients/{patient_id}/insurance",
    response_model=PatientInsuranceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a patient's insurance policy",
    dependencies=[Depends(RequirePermission("billing:manage_insurance"))],
    responses={400: {"description": "This exact policy is already recorded for this patient"}, 404: {"description": "Patient or provider not found"}},
)
def add_patient_insurance(patient_id: int, payload: PatientInsuranceCreate, db: Session = Depends(get_db)) -> PatientInsurance:
    if payload.patient_id != patient_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="patient_id in the URL and body must match")
    if db.get(PatientDetails, patient_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    if db.get(InsuranceProvider, payload.provider_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Insurance provider not found")

    duplicate = db.query(PatientInsurance).filter(
        PatientInsurance.patient_id == patient_id,
        PatientInsurance.provider_id == payload.provider_id,
        PatientInsurance.policy_number == payload.policy_number,
    ).first()
    if duplicate:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This exact policy is already recorded for this patient")

    policy = PatientInsurance(**payload.model_dump())
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return policy


@router.get(
    "/patients/{patient_id}/insurance",
    response_model=list[PatientInsuranceResponse],
    summary="List a patient's insurance policies",
    responses={403: {"description": "Not this patient or billing staff"}, 404: {"description": "Patient not found"}},
)
def list_patient_insurance(
    patient_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> list[PatientInsurance]:
    if db.get(PatientDetails, patient_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    _assert_billing_access(db, current_user, patient_id)
    return db.query(PatientInsurance).filter(PatientInsurance.patient_id == patient_id).all()
