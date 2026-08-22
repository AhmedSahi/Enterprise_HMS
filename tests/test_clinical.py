"""Tests for Module 4: Clinical & IPD."""
from datetime import date, timedelta

from tests.conftest import signup_plain_user


def _grant_doctor_permissions(client, auth_headers, user_id: int) -> None:
    # 1. Fetch or Create Doctor Role
    roles = client.get("/api/v1/roles", headers=auth_headers).json()
    doctor_role = next((r for r in roles if r["name"] == "doctor"), None)
    
    if doctor_role is None:
        doctor_role = client.post(
            "/api/v1/roles", 
            json={"name": "doctor", "description": "Treating physician"}, 
            headers=auth_headers
        ).json()

    # 2. Permissions HAMESHA assign karein (if condition ke BAHAR)
    needed_codes = {
        "clinical:manage_appointments", "clinical:manage_admissions", "clinical:manage_vitals",
        "clinical:manage_surgery", "clinical:manage_diagnoses", "clinical:manage_prescriptions",
        "profiles:manage_patient_allergies", "profiles:manage_medical_history",
    }
    
    all_perms = client.get("/api/v1/permissions", headers=auth_headers).json()
    for perm in all_perms:
        if perm["code"] in needed_codes:
            client.post(
                "/api/v1/permissions/assign",
                json={"role_id": doctor_role["id"], "permission_id": perm["id"]},
                headers=auth_headers,
            )

    # 3. User ko Role assign karein
    client.post(
        "/api/v1/roles/assign", 
        json={"user_id": user_id, "role_id": doctor_role["id"]}, 
        headers=auth_headers
    )


def _setup_doctor_and_patient(client, auth_headers, doctor_email="doc@hms.com", patient_email="pat@hms.com"):
    doc_user = signup_plain_user(client, doctor_email)
    pat_user = signup_plain_user(client, patient_email)
    _grant_doctor_permissions(client, auth_headers, doc_user["id"])
    staff = client.post(
        "/api/v1/staff",
        json={"user_id": doc_user["id"], "employee_code": f"EMP-{doc_user['id']}", "staff_type": "doctor", "license_number": f"LIC-{doc_user['id']}"},
        headers=auth_headers,
    ).json()
    patient = client.post(
        "/api/v1/patients", json={"user_id": pat_user["id"], "patient_code": f"MRN-{pat_user['id']}", "blood_group": "O+"}, headers=auth_headers
    ).json()
    return staff, patient


def _login(client, email, password="Plain123!"):
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _tomorrow():
    return (date.today() + timedelta(days=1)).isoformat()


# =========================================================================
# APPOINTMENTS
# =========================================================================
def test_patient_self_books_appointment(client, auth_headers):
    staff, _ = _setup_doctor_and_patient(client, auth_headers)
    signup_plain_user(client, "selfbook@hms.com")
    client.post(
        "/api/v1/patients",
        json={"user_id": client.get("/api/v1/users", headers=auth_headers).json()[-1]["id"], "patient_code": "MRN-SB", "blood_group": "A+"},
        headers=auth_headers,
    )
    headers = _login(client, "selfbook@hms.com")
    resp = client.post(
        "/api/v1/appointments",
        json={"doctor_id": staff["id"], "appointment_date": _tomorrow(), "appointment_time": "10:00:00"},
        headers=headers,
    )
    assert resp.status_code == 201


def test_double_booking_same_doctor_same_time_rejected(client, auth_headers):
    staff, _ = _setup_doctor_and_patient(client, auth_headers)
    p1_user = signup_plain_user(client, "p1@hms.com")
    p2_user = signup_plain_user(client, "p2@hms.com")
    client.post("/api/v1/patients", json={"user_id": p1_user["id"], "patient_code": "MRN-P1", "blood_group": "A+"}, headers=auth_headers)
    client.post("/api/v1/patients", json={"user_id": p2_user["id"], "patient_code": "MRN-P2", "blood_group": "B+"}, headers=auth_headers)

    h1 = _login(client, "p1@hms.com")
    h2 = _login(client, "p2@hms.com")

    first = client.post(
        "/api/v1/appointments",
        json={"doctor_id": staff["id"], "appointment_date": _tomorrow(), "appointment_time": "11:00:00"},
        headers=h1,
    )
    assert first.status_code == 201

    second = client.post(
        "/api/v1/appointments",
        json={"doctor_id": staff["id"], "appointment_date": _tomorrow(), "appointment_time": "11:15:00"},
        headers=h2,
    )
    assert second.status_code == 400  # overlaps first (30 min default duration)


def test_booking_in_the_past_rejected(client, auth_headers):
    staff, _ = _setup_doctor_and_patient(client, auth_headers)
    pat_user = signup_plain_user(client, "pastbook@hms.com")
    client.post("/api/v1/patients", json={"user_id": pat_user["id"], "patient_code": "MRN-PAST", "blood_group": "A+"}, headers=auth_headers)
    headers = _login(client, "pastbook@hms.com")
    resp = client.post(
        "/api/v1/appointments",
        json={"doctor_id": staff["id"], "appointment_date": "2020-01-01", "appointment_time": "09:00:00"},
        headers=headers,
    )
    assert resp.status_code == 400


def test_reception_booking_on_behalf_requires_permission(client, auth_headers):
    staff, patient = _setup_doctor_and_patient(client, auth_headers, patient_email="onbehalf@hms.com")
    plain_receptionist = signup_plain_user(client, "reception@hms.com")
    headers = _login(client, "reception@hms.com")

    # no clinical:manage_appointments permission yet -> forbidden
    resp = client.post(
        "/api/v1/appointments",
        json={"patient_id": patient["id"], "doctor_id": staff["id"], "appointment_date": _tomorrow(), "appointment_time": "09:00:00"},
        headers=headers,
    )
    assert resp.status_code == 403


def test_appointment_status_state_machine(client, auth_headers):
    staff, _ = _setup_doctor_and_patient(client, auth_headers, patient_email="sm@hms.com")
    pat_user = signup_plain_user(client, "sm_patient@hms.com")
    client.post("/api/v1/patients", json={"user_id": pat_user["id"], "patient_code": "MRN-SM", "blood_group": "A+"}, headers=auth_headers)
    headers = _login(client, "sm_patient@hms.com")

    appt = client.post(
        "/api/v1/appointments",
        json={"doctor_id": staff["id"], "appointment_date": _tomorrow(), "appointment_time": "12:00:00"},
        headers=headers,
    ).json()

    # pending -> completed directly is NOT allowed (must go through confirmed)
    bad = client.patch(f"/api/v1/appointments/{appt['id']}/status", json={"status": "completed"}, headers=auth_headers)
    assert bad.status_code == 400

    ok1 = client.patch(f"/api/v1/appointments/{appt['id']}/status", json={"status": "confirmed"}, headers=auth_headers)
    assert ok1.status_code == 200

    ok2 = client.patch(f"/api/v1/appointments/{appt['id']}/status", json={"status": "completed"}, headers=auth_headers)
    assert ok2.status_code == 200

    # completed is terminal -> further changes rejected
    terminal = client.patch(f"/api/v1/appointments/{appt['id']}/status", json={"status": "cancelled"}, headers=auth_headers)
    assert terminal.status_code == 400


# =========================================================================
# ADMISSIONS + BED OCCUPANCY
# =========================================================================
def _make_bed(client, auth_headers):
    dept = client.post("/api/v1/departments", json={"name": "Cardiology"}, headers=auth_headers).json()
    ward = client.post(
        "/api/v1/wards", json={"department_id": dept["id"], "name": "W1", "ward_type": "general", "total_capacity": 5},
        headers=auth_headers,
    ).json()
    return client.post("/api/v1/beds", json={"bed_number": "A1", "ward_id": ward["id"]}, headers=auth_headers).json()


def test_admit_patient_marks_bed_occupied(client, auth_headers):
    staff, patient = _setup_doctor_and_patient(client, auth_headers, patient_email="admit1@hms.com")
    bed = _make_bed(client, auth_headers)

    resp = client.post(
        "/api/v1/admissions",
        json={"patient_id": patient["id"], "bed_id": bed["id"], "admitted_by_doctor_id": staff["id"], "admission_date": "2026-01-01T09:00:00"},
        headers=auth_headers,
    )
    assert resp.status_code == 201

    bed_after = client.get(f"/api/v1/beds/{bed['id']}", headers=auth_headers).json()
    assert bed_after["is_occupied"] is True


def test_admit_to_occupied_bed_rejected(client, auth_headers):
    staff, patient1 = _setup_doctor_and_patient(client, auth_headers, patient_email="occ1@hms.com")
    pat2_user = signup_plain_user(client, "occ2@hms.com")
    patient2 = client.post("/api/v1/patients", json={"user_id": pat2_user["id"], "patient_code": "MRN-OCC2", "blood_group": "B+"}, headers=auth_headers).json()
    bed = _make_bed(client, auth_headers)

    client.post(
        "/api/v1/admissions",
        json={"patient_id": patient1["id"], "bed_id": bed["id"], "admission_date": "2026-01-01T09:00:00"},
        headers=auth_headers,
    )
    resp = client.post(
        "/api/v1/admissions",
        json={"patient_id": patient2["id"], "bed_id": bed["id"], "admission_date": "2026-01-01T10:00:00"},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_patient_cannot_have_two_active_admissions(client, auth_headers):
    staff, patient = _setup_doctor_and_patient(client, auth_headers, patient_email="dual_admit@hms.com")
    bed1 = _make_bed(client, auth_headers)
    dept2 = client.post("/api/v1/departments", json={"name": "Neuro"}, headers=auth_headers).json()
    ward2 = client.post(
        "/api/v1/wards", json={"department_id": dept2["id"], "name": "W2", "ward_type": "general", "total_capacity": 5},
        headers=auth_headers,
    ).json()
    bed2 = client.post("/api/v1/beds", json={"bed_number": "B2", "ward_id": ward2["id"]}, headers=auth_headers).json()

    client.post(
        "/api/v1/admissions",
        json={"patient_id": patient["id"], "bed_id": bed1["id"], "admission_date": "2026-01-01T09:00:00"},
        headers=auth_headers,
    )
    resp = client.post(
        "/api/v1/admissions",
        json={"patient_id": patient["id"], "bed_id": bed2["id"], "admission_date": "2026-01-01T09:00:00"},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_discharge_frees_bed(client, auth_headers):
    staff, patient = _setup_doctor_and_patient(client, auth_headers, patient_email="discharge1@hms.com")
    bed = _make_bed(client, auth_headers)

    admission = client.post(
        "/api/v1/admissions",
        json={"patient_id": patient["id"], "bed_id": bed["id"], "admission_date": "2026-01-01T09:00:00"},
        headers=auth_headers,
    ).json()

    resp = client.patch(f"/api/v1/admissions/{admission['id']}/status", json={"status": "discharged"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["discharge_date"] is not None

    bed_after = client.get(f"/api/v1/beds/{bed['id']}", headers=auth_headers).json()
    assert bed_after["is_occupied"] is False


# =========================================================================
# CLINICAL ACCESS SCOPING (diagnoses / prescriptions / vitals)
# =========================================================================
def test_doctor_can_only_diagnose_own_patients(client, auth_headers):
    staff_a, patient = _setup_doctor_and_patient(client, auth_headers, doctor_email="diag_doc_a@hms.com", patient_email="diag_pat@hms.com")
    doc_b_user = signup_plain_user(client, "diag_doc_b@hms.com")
    _grant_doctor_permissions(client, auth_headers, doc_b_user["id"])  # doc_b has the RIGHT KIND of permission...
    client.post(
        "/api/v1/staff", json={"user_id": doc_b_user["id"], "employee_code": "D2", "staff_type": "doctor", "license_number": "L2"},
        headers=auth_headers,
    )

    pat_user_id = client.get("/api/v1/patients", headers=auth_headers).json()
    appt_headers = _login(client, "diag_pat@hms.com")
    appt = client.post(
        "/api/v1/appointments",
        json={"doctor_id": staff_a["id"], "patient_id": patient["id"], "appointment_date": _tomorrow(), "appointment_time": "09:00:00"},
        headers=auth_headers,
    ).json()

    doc_a_headers = _login(client, "diag_doc_a@hms.com")
    ok = client.post(
        "/api/v1/diagnoses",
        json={"appointment_id": appt["id"], "icd_code": "J00", "description": "Common cold"},
        headers=doc_a_headers,
    )

    assert ok.status_code == 201

    

    doc_b_headers = _login(client, "diag_doc_b@hms.com")
    blocked = client.post(
        "/api/v1/diagnoses",
        json={"appointment_id": appt["id"], "icd_code": "J01", "description": "Should be blocked"},
        headers=doc_b_headers,
    )
    assert blocked.status_code == 403


# =========================================================================
# PRESCRIPTIONS + PHARMACY STOCK
# =========================================================================
def _setup_prescription_context(client, auth_headers, doctor_email="rx_doc@hms.com", patient_email="rx_pat@hms.com"):
    staff, patient = _setup_doctor_and_patient(client, auth_headers, doctor_email=doctor_email, patient_email=patient_email)
    appt_headers = _login(client, patient_email)
    appt = client.post(
        "/api/v1/appointments",
        json={"doctor_id": staff["id"], "patient_id": patient["id"], "appointment_date": _tomorrow(), "appointment_time": "09:00:00"},
        headers=auth_headers,
    ).json()
    return staff, patient, appt


def test_prescription_deducts_stock_fefo(client, auth_headers):
    staff, patient, appt = _setup_prescription_context(client, auth_headers)

    med = client.post(
        "/api/v1/medications", json={"name": "Amoxicillin", "dosage_form": "capsule", "strength": "250mg", "unit_price": 5},
        headers=auth_headers,
    ).json()
    soon = (date.today() + timedelta(days=10)).isoformat()
    far = (date.today() + timedelta(days=100)).isoformat()
    batch_soon = client.post(
        f"/api/v1/medications/{med['id']}/batches",
        json={"medication_id": med["id"], "batch_number": "SOON", "expiry_date": soon, "quantity_available": 5},
        headers=auth_headers,
    ).json()
    client.post(
        f"/api/v1/medications/{med['id']}/batches",
        json={"medication_id": med["id"], "batch_number": "FAR", "expiry_date": far, "quantity_available": 20},
        headers=auth_headers,
    )

    doc_headers = _login(client, "rx_doc@hms.com")
    resp = client.post(
        "/api/v1/prescriptions",
        json={
            "appointment_id": appt["id"], "patient_id": patient["id"], "notes": "Take with food",
            "items": [{"medication_id": med["id"], "dosage_instructions": "1 cap 3x/day", "duration_days": 7, "quantity": 10}],
        },
        headers=doc_headers,
    )

    assert resp.status_code == 201

    # FEFO: the 5-unit SOON batch should be fully drained first, then 5 more taken from FAR
    batches = client.get(f"/api/v1/medications/{med['id']}/batches", headers=auth_headers).json()
    by_number = {b["batch_number"]: b["quantity_available"] for b in batches}
    assert by_number["SOON"] == 0
    assert by_number["FAR"] == 15


def test_prescription_insufficient_stock_rejected_atomically(client, auth_headers):
    staff, patient, appt = _setup_prescription_context(client, auth_headers, doctor_email="rx_doc2@hms.com", patient_email="rx_pat2@hms.com")

    med_ok = client.post(
        "/api/v1/medications", json={"name": "Paracetamol", "dosage_form": "tablet", "strength": "500mg", "unit_price": 1},
        headers=auth_headers,
    ).json()
    future = (date.today() + timedelta(days=90)).isoformat()
    client.post(
        f"/api/v1/medications/{med_ok['id']}/batches",
        json={"medication_id": med_ok["id"], "batch_number": "B1", "expiry_date": future, "quantity_available": 100},
        headers=auth_headers,
    )

    med_short = client.post(
        "/api/v1/medications", json={"name": "RareDrug", "dosage_form": "tablet", "strength": "10mg", "unit_price": 50},
        headers=auth_headers,
    ).json()
    client.post(
        f"/api/v1/medications/{med_short['id']}/batches",
        json={"medication_id": med_short["id"], "batch_number": "B1", "expiry_date": future, "quantity_available": 2},
        headers=auth_headers,
    )

    doc_headers = _login(client, "rx_doc2@hms.com")
    resp = client.post(
        "/api/v1/prescriptions",
        json={
            "appointment_id": appt["id"], "patient_id": patient["id"],
            "items": [
                {"medication_id": med_ok["id"], "dosage_instructions": "1 tab", "duration_days": 5, "quantity": 5},
                {"medication_id": med_short["id"], "dosage_instructions": "1 tab", "duration_days": 5, "quantity": 10},  # only 2 in stock
            ],
        },
        headers=doc_headers,
    )
    assert resp.status_code == 400

    # atomicity check: the plentiful medication's stock must be UNCHANGED since the whole request was rejected
    batches = client.get(f"/api/v1/medications/{med_ok['id']}/batches", headers=auth_headers).json()
    assert batches[0]["quantity_available"] == 100


# =========================================================================
# SURGERY OVERLAP
# =========================================================================
def test_ot_double_booking_rejected(client, auth_headers):
    staff, patient = _setup_doctor_and_patient(client, auth_headers, doctor_email="surgeon@hms.com", patient_email="surg_pat@hms.com")
    ot = client.post("/api/v1/operation-theaters", json={"name_or_code": "OT-1"}, headers=auth_headers).json()

    first = client.post(
        "/api/v1/ot-schedules",
        json={"ot_id": ot["id"], "patient_id": patient["id"], "lead_surgeon_id": staff["id"],
              "scheduled_start": "2026-02-01T09:00:00", "scheduled_end": "2026-02-01T11:00:00"},
        headers=auth_headers,
    )
    assert first.status_code == 201

    overlap = client.post(
        "/api/v1/ot-schedules",
        json={"ot_id": ot["id"], "patient_id": patient["id"], "lead_surgeon_id": staff["id"],
              "scheduled_start": "2026-02-01T10:00:00", "scheduled_end": "2026-02-01T12:00:00"},
        headers=auth_headers,
    )
    assert overlap.status_code == 400
