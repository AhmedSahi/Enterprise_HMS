# Enterprise Hospital Management System (HMS) Backend

A production-grade, modular FastAPI backend combining Enterprise-grade Identity & Access Management (IAM) with a comprehensive Hospital Management System. Built with PostgreSQL, SQLAlchemy ORM, and Alembic for database migrations.

##  Key Modules & Features

### 1. **Identity & Access Management (IAM)**
- **Role-Based Access Control (RBAC):** Multi-level permission system supporting Admin, Manager, Doctor, Patient, Receptionist roles
- **JWT Authentication:** Secure token-based authentication with refresh token rotation
- **User Management:** Email-based users with password hashing using bcrypt
- **Audit Logs:** Immutable activity trail for compliance and monitoring
- **Permission Management:** Fine-grained permission codes (e.g., `bloodbank:approve`)

### 2. **User Profiles & Identity**
- **Unified Profile System:** Single user can be staff, patient, or both
- **Patient Profiles:** Medical Record Number (MRN), blood group, linked to health records
- **Staff Details:** Department assignment, specialization, license tracking for doctors
- **Contact Information:** Emergency contacts, phone numbers, addresses
- **Allergy Management:** Normalized allergen database with severity levels
- **Medical History:** Chronic conditions and medical background tracking

### 3. **Clinical Operations**
- **Doctor Schedules:** Weekly recurring availability slots for appointments
- **Appointments (OPD):** Out-patient clinic scheduling with status tracking
- **Admissions (IPD):** In-patient stays with bed management and transfers
- **Discharge Summaries:** Final clinical notes with follow-up instructions
- **Vitals Monitoring:** Blood pressure, temperature, pulse, SpO2 tracking
- **Diagnoses:** ICD-coded diagnoses linked to appointments or admissions
- **Prescriptions:** Medicine prescriptions tied to visits with itemized details

### 4. **Hospital Infrastructure**
- **Departments:** Organizational units with managers and staff
- **Wards:** Patient halls (general, ICU, isolation) with capacity management
- **Rooms:** Private/semi-private rooms with daily rates
- **Beds:** Physical beds tracked with occupancy status and location
- **Bed Transfers:** Movement history during patient stays
- **Operation Theaters:** Surgery suites with status tracking and team assignment

### 5. **Pharmacy & Inventory**
- **Medication Catalog:** Drug database with dosage, strength, and pricing
- **Batch Management:** Track medication batches with expiry dates and stock levels
- **Prescription Items:** Itemized prescription details linked to medications

### 6. **Billing & Finance**
- **Invoices:** Comprehensive patient bills linked to appointments or admissions
- **Invoice Items:** Itemized charges (consultation, room, medicine, lab, OT)
- **Payments:** Multiple payment methods (cash, card, bank transfer, insurance)
- **Insurance Management:** TPA providers and patient policy tracking
- **Payment Tracking:** Partial and full payment status management

### 7. **Blood Bank Management**
- **Inventory Tracking:** Real-time blood unit availability by blood group
- **Blood Requests:** Patient blood requests with approval workflow
- **Request Status:** Pending → Approved/Rejected state machine

---

##  Database Schema Overview

### Module 1: IAM & Security

| Table | Purpose | Key Fields |
|-------|---------|-----------|
| `users` | Authentication identity | email, hashed_password, is_active |
| `roles` | Named roles (admin, doctor, patient) | name, description |
| `permissions` | Fine-grained permission codes | name, code (unique) |
| `user_roles` | Many-to-many: users ↔ roles | user_id, role_id |
| `role_permissions` | Many-to-many: roles ↔ permissions | role_id, permission_id |
| `refresh_tokens` | Session management & revocation | token, expires_at, revoked |
| `audit_logs` | Immutable activity trail | action, resource_type, user_id, status |

### Module 2: User Profiles & Identity

| Table | Purpose | Key Fields |
|-------|---------|-----------|
| `user_profiles` | Personal info (name, DOB, gender) | user_id (1:1), first_name, last_name, dob, cnic |
| `user_contacts` | Contact details for all users | user_id (1:1), primary_phone, emergency_contact |
| `staff_details` | Employment metadata | user_id (1:1), department_id, employee_code, staff_type, specialization |
| `patient_details` | Hospital-specific patient data | user_id (1:1), patient_code (MRN), blood_group |
| `allergens` | Master list of known allergens | name, category (drug/food/environmental) |
| `patient_allergies` | Patient's allergen links | patient_id, allergen_id, severity, reaction_notes |
| `patient_medical_history` | Chronic/past conditions | patient_id, condition, status (active/resolved/chronic) |

### Module 3: Hospital Infrastructure

| Table | Purpose | Key Fields |
|-------|---------|-----------|
| `departments` | Organizational units | name, manager_id |
| `wards` | Patient halls | department_id, name, ward_type, total_capacity |
| `rooms` | Private/semi-private rooms | room_number, room_type, floor, daily_rate, status |
| `beds` | Physical beds | bed_number, ward_id OR room_id (CHECK constraint), is_occupied |
| `bed_transfers` | Patient movement history | admission_id, from_bed_id, to_bed_id, transferred_at |
| `operation_theaters` | Surgery suites | name_or_code, department_id, floor, status |

### Module 4: Clinical Operations

| Table | Purpose | Key Fields |
|-------|---------|-----------|
| `doctor_schedules` | Weekly recurring availability | doctor_id, day_of_week, start_time, end_time, slot_duration_minutes |
| `appointments` | OPD consultations | patient_id, doctor_id, appointment_date, status |
| `admissions` | IPD stays | patient_id, bed_id, admission_date, discharge_date, status |
| `discharge_summaries` | Clinical exit notes | admission_id (1:1), final_diagnosis, treatment_given, follow_up_instructions |
| `vitals_logs` | Vital signs recordings | patient_id, admission_id (nullable), bp_systolic, bp_diastolic, temperature, pulse, spo2 |
| `ot_schedules` | Booked surgery slots | ot_id, patient_id, lead_surgeon_id, scheduled_start, status |
| `ot_team_members` | Surgery team members | ot_schedule_id, staff_id, role_in_surgery (anesthetist/assistant/nurse) |
| `diagnoses` | ICD-coded diagnoses | appointment_id OR admission_id, icd_code, description |
| `prescriptions` | Medicine orders | appointment_id OR admission_id, patient_id, status |
| `prescription_items` | Individual medicines in prescriptions | prescription_id, medication_id, quantity, dosage, duration |

### Module 5: Pharmacy & Inventory

| Table | Purpose | Key Fields |
|-------|---------|-----------|
| `medications` | Drug catalog | name, generic_name, dosage_form, strength, unit_price |
| `medication_batches` | Physical stock batches | medication_id, batch_number, expiry_date, quantity_available |

### Module 6: Billing & Finance

| Table | Purpose | Key Fields |
|-------|---------|-----------|
| `invoices` | Patient bills | patient_id, appointment_id/admission_id, total_amount, paid_amount, status |
| `invoice_items` | Itemized charges | invoice_id, item_type (consultation/room/medicine/lab/ot), amount |
| `payments` | Payment transactions | invoice_id, amount_paid, payment_method, transaction_date |
| `insurance_providers` | TPA/insurance companies | name, contact_info |
| `patient_insurance` | Active patient policies | patient_id, provider_id, policy_number, coverage_details |

### Module 7: Blood Bank

| Table | Purpose | Key Fields |
|-------|---------|-----------|
| `blood_inventory` | Stock by blood group | blood_group (unique), available_units, last_updated |
| `blood_requests` | Patient blood requests | patient_id, blood_group, units_required, status (pending/approved/rejected) |

---

##  Key Relationships & Constraints

### One-to-One Relationships (1:1)
- `User` → `UserProfile` (every user has exactly one profile)
- `User` → `UserContact` (every user has exactly one contact)
- `User` → `StaffDetails` (if staff; nullable for patients-only)
- `User` → `PatientDetails` (if patient; nullable for staff-only)
- `Admission` → `DischargeSummary` (discharge notes only when admitted ends)

### One-to-Many Relationships (1:N)
- `User` → `RefreshTokens` (multiple active sessions per user)
- `User` → `AuditLogs` (many actions per user)
- `Department` → `Staff` (many staff in one dept)
- `Department` → `Wards` (many wards per dept)
- `Ward` → `Beds` (many beds per ward)
- `Room` → `Beds` (many beds per room)
- `Medication` → `MedicationBatch` (multiple batches per drug)
- `PatientDetails` → `Allergies` (many allergens per patient)
- `PatientDetails` → `MedicalHistory` (many conditions per patient)
- `Invoice` → `InvoiceItems` (many charges per bill)
- `Invoice` → `Payments` (multiple payments per invoice)
- `Appointment` → `Diagnoses` (multiple diagnoses per visit)
- `Admission` → `Diagnoses` (multiple diagnoses per stay)
- `Admission` → `BedTransfers` (movement history)
- `Admission` → `VitalsLogs` (multiple recordings)

### Many-to-Many Relationships (M:N)
- `User` ↔ `Role` via `user_roles` (users can have multiple roles)
- `Role` ↔ `Permission` via `role_permissions` (roles have multiple permissions)

### Business Logic Constraints
- **Bed Location Exclusivity (CHECK constraint):** Each bed belongs to EITHER a ward OR a room, never both
- **Diagnosis Source (CHECK constraint):** Each diagnosis links to EITHER an appointment OR an admission
- **Only Active/Valid Records:** Soft delete via relationship cascade policies
- **Timestamp Audit Trail:** All tables have `created_at` and `updated_at` fields

---

##  Project Structure

```
Enterprise_HMS/
├── alembic/                       # Database migrations
│   ├── env.py                     # Migration environment config
│   ├── script.py.mako            # Migration template
│   └── versions/
│       └── 821ac6887ce5_initial_schema.py
├── src/
│   ├── api/
│   │   └── v1/
│   │       └── auth.py           # Authentication endpoints
│   ├── core/
│   │   ├── config.py             # Settings (env-based)
│   │   ├── database.py           # SQLAlchemy engine & session
│   │   ├── deps.py               # Dependency injection
│   │   └── security.py           # JWT & password hashing
│   ├── db/
│   │   ├── seed_data.json        # Sample data
│   │   └── seed.py               # Data seeding script
│   ├── models/
│   │   ├── base.py               # Base model & mixins
│   │   ├── IAM.py                # Module 1: Users, Roles, Permissions
│   │   ├── profile.py            # Module 2: User profiles & identity
│   │   ├── infrastructure.py     # Module 3: Depts, wards, beds, OTs
│   │   ├── clinical.py           # Module 4: Appointments, admissions, diagnoses
│   │   ├── pharmacy.py           # Module 5: Medications & inventory
│   │   ├── billing.py            # Module 6: Invoices & payments
│   │   └── blood_bank.py         # Module 7: Blood inventory & requests
│   └── schemas/                  # Pydantic request/response models (mirrors models/)
├── main.py                        # FastAPI app entry point
├── alembic.ini                    # Alembic configuration
├── requirements.txt              # Python dependencies
└── README.md                      # This file
```

---

##  Installation & Setup

### Prerequisites
- Python 3.10+
- PostgreSQL 12+
- pip or Poetry

### Setup Steps

1. **Clone & navigate to project:**
   ```bash
   cd Enterprise_HMS
   ```

2. **Create virtual environment:**
   ```bash
   python -m venv .venv
   # Windows
   .venv\Scripts\activate
   # macOS/Linux
   source .venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Create `.env` file:**
   ```env
   DATABASE_URL=postgresql://user:password@localhost/hms_db
   SECRET_KEY=your-super-secret-key-here
   ALGORITHM=HS256
   ACCESS_TOKEN_EXPIRE_MINUTES=30
   REFRESH_TOKEN_EXPIRE_DAYS=7
   ```

5. **Initialize database:**
   ```bash
   # Create database
   createdb hms_db
   
   # Run migrations
   python -m alembic upgrade head
   ```

6. **Seed sample data (optional):**
   ```bash
   python src/db/seed.py
   ```

7. **Run server:**
   ```bash
   python main.py
   # Or with uvicorn
   uvicorn main:app --reload
   ```

The API will be available at `http://localhost:8000` with documentation at `/docs` (Swagger) and `/redoc` (ReDoc).

---

##  Authentication & Authorization

### JWT Token Flow
1. User logs in with email/password
2. Server returns `access_token` (short-lived, 30 min default) and `refresh_token` (long-lived, 7 days)
3. Client includes access token in `Authorization: Bearer <token>` header
4. When access token expires, use refresh token to get new access token
5. User can logout to revoke all refresh tokens

### Role-Based Access Control (RBAC)
- **Roles:** admin, manager, doctor, nurse, receptionist, patient, lab_tech, pharmacist
- **Permissions:** Code-based (e.g., `bloodbank:approve`, `patient:read`)
- **Enforcement:** FastAPI dependency injection validates user roles/permissions on each endpoint

### Audit Logging
All sensitive actions are logged with:
- User who performed the action
- Action type (e.g., "bloodbank:approve")
- Resource affected (type and ID)
- IP address
- Timestamp
- Success/failure status

---

##  Database Design Principles

### Normalization
- **1NF/2NF/3NF compliant:** Minimal data duplication
- **Allergen Master List:** Reusable across all patients (normalized)
- **Insurance Providers:** Master table, not patient-specific

### Separation of Concerns
- **Module-based:** Each module handles one domain (IAM, clinical, billing, etc.)
- **Profile vs. Auth:** `User` handles authentication only; `UserProfile`/`StaffDetails`/`PatientDetails` handle identity

### Flexibility & Extensibility
- **Soft Cascades:** Foreign keys use cascade delete/set null for safe data retention
- **Nullable Fields:** Optional relationships (e.g., middle name, secondary phone)
- **Enums:** Strong typing for statuses and categories (Python + DB enums)
- **Check Constraints:** Database-level validation (e.g., bed location exclusivity)

### Auditability
- **Timestamps:** `created_at` and `updated_at` on all records
- **Audit Logs:** Immutable transaction trail for compliance
- **Soft Delete:** Relationship cascades preserve data integrity during deletions

---

##  State Machines & Workflows

### Appointment Status
```
PENDING → CONFIRMED → COMPLETED or CANCELLED
```

### Admission Status
```
ADMITTED → DISCHARGED or TRANSFERRED
```

### Invoice Status
```
UNPAID → PARTIALLY_PAID → PAID or CANCELLED
```

### Blood Request Status
```
PENDING → APPROVED or REJECTED
```

### Operation Theater Status
```
AVAILABLE ↔ IN_USE ↔ MAINTENANCE
```

---

##  Example Data Flows

### Patient Registration Flow
1. Create `User` (email + password)
2. Create `UserProfile` (first name, DOB, gender)
3. Create `UserContact` (phone, address)
4. Create `PatientDetails` (blood group, MRN)
5. Assign `patient` role to user
6. Store allergies in `PatientAllergy` + `Allergen`

### Appointment & Billing Flow
1. Patient books `Appointment` with doctor
2. Doctor records `Diagnosis` (ICD code)
3. Doctor issues `Prescription` with `PrescriptionItems`
4. System auto-creates `Invoice` with itemized charges
5. Patient makes `Payment` (partial or full)
6. Invoice status updated based on paid_amount vs total_amount

### Admission & Discharge Flow
1. Doctor admits patient: create `Admission` with `Bed`
2. Nurse records `VitalsLog` regularly during stay
3. Patient transferred between beds: create `BedTransfer` record
4. On discharge, doctor creates `DischargeSummary`
5. System auto-updates `Admission` status to DISCHARGED

---

##  Current Status

-  Database schema fully defined with Alembic migrations
-  All 7 modules modeled (IAM, Profiles, Infrastructure, Clinical, Pharmacy, Billing, Blood Bank)
-  Relationships and constraints implemented
-  TimestampMixin for audit trail
-  API endpoints in development (auth.py started)
-  Pydantic schemas being created

---


# Current Structure

---

**Last Updated:** 2026-08-13
│   │   ├── audit.py
│   │   ├── base.py
│   │   ├── billing.py
│   │   ├── blood_bank.py
│   │   ├── clinical.py
│   │   ├── profile.py
│   │   ├── role.py
│   │   └── user.py
│   └── schemas/           # Pydantic data validation schemas
│       ├── billing.py
│       ├── blood_bank.py
│       ├── clinical.py
│       ├── profile.py
│       ├── role.py
│       ├── token.py
│       └── user.py
├── .env                  # Environment secrets (Git-ignored)
├── .env.example          # Sample environment variables configuration
├── .gitignore            # Git exclusion definitions
├── alembic.ini           # Alembic configuration file
├── main.py               # FastAPI application entry point
├── HMS_Schema.png        # Complete database schema diagram
└── requirements.txt      # Project Python dependencies
