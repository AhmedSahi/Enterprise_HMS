# Enterprise HMS - Schema Quick Reference

## 🎯 Core Entity Relationships

```
┌─────────────────────────────────────────────────────────┐
│                    USERS (Authentication)                │
│  ┌──────────────────────────────────────────────────┐   │
│  │ id | email | hashed_password | is_active |       │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
         │
         ├─→ ROLES (Many-to-Many via user_roles)
         │   └─→ PERMISSIONS (Many-to-Many via role_permissions)
         │
         ├─→ USER_PROFILES (1:1)
         │   └─ first_name, last_name, gender, dob, cnic
         │
         ├─→ USER_CONTACTS (1:1)
         │   └─ phone, address, emergency_contact
         │
         ├─→ STAFF_DETAILS (1:1) ─→ DEPARTMENTS (N:1)
         │   └─ employee_code, staff_type, specialization, license
         │
         ├─→ PATIENT_DETAILS (1:1)
         │   ├─→ PATIENT_ALLERGIES
         │   │   └─→ ALLERGENS
         │   ├─→ PATIENT_MEDICAL_HISTORY
         │   └─→ BLOOD_REQUESTS
         │
         ├─→ REFRESH_TOKENS (1:N)
         │   └─ token, expires_at, revoked
         │
         └─→ AUDIT_LOGS (1:N)
             └─ action, resource_type, resource_id, status
```

---

## 🏥 Hospital Infrastructure

```
DEPARTMENTS
  ├─→ STAFF_DETAILS (N:1)
  ├─→ WARDS (1:N)
  │   └─→ BEDS (1:N)
  │       └─→ ADMISSIONS (1:N)
  │           ├─→ DISCHARGE_SUMMARIES (1:1)
  │           ├─→ BED_TRANSFERS (1:N)
  │           ├─→ VITALS_LOGS (1:N)
  │           ├─→ DIAGNOSES (1:N)
  │           ├─→ PRESCRIPTIONS (1:N)
  │           └─→ INVOICES (1:N)
  │
  ├─→ ROOMS (1:N)
  │   └─→ BEDS (1:N)
  │       └─→ ADMISSIONS (1:N)
  │
  └─→ OPERATION_THEATERS (1:N)
      └─→ OT_SCHEDULES (1:N)
          └─→ OT_TEAM_MEMBERS (1:N)
              └─→ STAFF_DETAILS (N:1)
```

---

## 👨‍⚕️ Clinical Operations

```
APPOINTMENTS (OPD)
  ├─→ PATIENT_DETAILS
  ├─→ STAFF_DETAILS (doctor)
  ├─→ DIAGNOSES (1:N)
  ├─→ PRESCRIPTIONS (1:N)
  │   └─→ PRESCRIPTION_ITEMS (1:N)
  │       └─→ MEDICATIONS
  └─→ INVOICES (1:N)

ADMISSIONS (IPD)
  ├─→ PATIENT_DETAILS
  ├─→ BEDS
  ├─→ STAFF_DETAILS (admitted_by_doctor)
  ├─→ DISCHARGE_SUMMARIES (1:1)
  ├─→ VITALS_LOGS (1:N)
  ├─→ BED_TRANSFERS (1:N)
  ├─→ DIAGNOSES (1:N)
  ├─→ PRESCRIPTIONS (1:N)
  │   └─→ PRESCRIPTION_ITEMS (1:N)
  │       └─→ MEDICATIONS
  └─→ INVOICES (1:N)

DOCTOR_SCHEDULES
  └─→ STAFF_DETAILS (doctor)
```

---

## 💊 Pharmacy & Medications

```
MEDICATIONS
  ├─→ MEDICATION_BATCHES (1:N)
  │   └─ batch_number, expiry_date, quantity_available
  └─→ PRESCRIPTION_ITEMS (1:N)
      └─→ PRESCRIPTIONS
```

---

## 💰 Billing & Finance

```
INVOICES
  ├─→ PATIENT_DETAILS
  ├─→ APPOINTMENTS (nullable, OPD invoice)
  ├─→ ADMISSIONS (nullable, IPD invoice)
  ├─→ INVOICE_ITEMS (1:N)
  │   └─ item_type, quantity, unit_price, amount
  └─→ PAYMENTS (1:N)
      └─→ USERS (processed_by)

PATIENT_INSURANCE
  ├─→ PATIENT_DETAILS
  └─→ INSURANCE_PROVIDERS
```

---

## 🩸 Blood Bank

```
BLOOD_INVENTORY
  └─ blood_group, available_units

BLOOD_REQUESTS
  ├─→ PATIENT_DETAILS
  ├─→ STAFF_DETAILS (requested_by_doctor)
  └─→ USERS (processed_by, blood_bank_staff)
```

---

## 📊 Key Cardinalities

| Relationship | Pattern | Example |
|--------------|---------|---------|
| User ↔ Role | Many-to-Many | User can have multiple roles (doctor + admin) |
| Role ↔ Permission | Many-to-Many | Role has multiple permissions |
| User → Profile | One-to-One | Each user has exactly one profile |
| Department → Staff | One-to-Many | One department has many staff |
| Doctor → Schedule | One-to-Many | One doctor has multiple schedule slots |
| Appointment → Diagnosis | One-to-Many | One visit can have multiple diagnoses |
| Prescription → Items | One-to-Many | One prescription has multiple medicines |
| Invoice → Items | One-to-Many | One bill has multiple charges |
| Invoice → Payments | One-to-Many | Bill can receive multiple partial payments |
| Admission → Transfers | One-to-Many | Patient moved between beds during stay |

---

## 🔐 RBAC Hierarchy

```
ROLES:
├── admin
│   └─ Full system access
├── manager
│   └─ Department management
├── doctor
│   └─ Clinical operations, prescriptions
├── nurse
│   └─ Patient care, vitals
├── receptionist
│   └─ Appointments, check-in
├── lab_tech
│   └─ Lab tests, results
├── pharmacist
│   └─ Medication dispensing
├── blood_bank_manager
│   └─ Blood inventory, approvals
└── patient
    └─ View own records

PERMISSIONS (examples):
├── bloodbank:approve
├── bloodbank:view
├── patient:read
├── patient:write
├── prescription:create
├── invoice:approve
└── audit:view
```

---

## 📋 State Machines

### Appointment
```
PENDING → CONFIRMED → COMPLETED
              ↘ CANCELLED
```

### Admission
```
ADMITTED → DISCHARGED
         → TRANSFERRED
```

### Invoice
```
UNPAID → PARTIALLY_PAID → PAID
  ↓                         ↑
  └─────→ CANCELLED ────────┘
```

### Blood Request
```
PENDING → APPROVED
       → REJECTED
```

### Operation Theater Status
```
AVAILABLE ↔ IN_USE ↔ MAINTENANCE
```

---

## 🔍 Quick Data Access Patterns

### Find Patient Info
```
USER
  → USER_PROFILE (name, DOB)
  → USER_CONTACT (phone)
  → PATIENT_DETAILS (MRN, blood group)
    → PATIENT_ALLERGIES (allergen severity)
    → PATIENT_MEDICAL_HISTORY (chronic conditions)
    → APPOINTMENTS (OPD visits)
    → ADMISSIONS (IPD stays)
```

### Get Patient's Recent Admission
```
PATIENT_DETAILS
  → ADMISSIONS (LIMIT 1, ORDER BY admission_date DESC)
    → BEDS (room/ward)
    → BED_TRANSFERS (movement history)
    → VITALS_LOGS (health monitoring)
    → DISCHARGE_SUMMARY
    → PRESCRIPTIONS
    → INVOICES
```

### Calculate Bill Total
```
INVOICE
  → INVOICE_ITEMS (SUM amount)
  → PAYMENTS (SUM amount_paid)
  → status (based on total vs paid)
```

### Check Doctor Availability
```
DOCTOR_SCHEDULE (day_of_week, start_time, end_time)
  → APPOINTMENTS (check booked slots)
  → Available slots = doctor_schedule slots - booked appointments
```

### Blood Bank Operations
```
BLOOD_REQUESTS
  → Check status (PENDING → APPROVED)
  → If approved: BLOOD_INVENTORY (decrement available_units)
  → Track in audit logs
```

---

## ⚡ Important Constraints

### Database-Level (CHECK)
1. **Bed Location** (beds table):
   ```sql
   (ward_id IS NOT NULL AND room_id IS NULL) 
   OR (ward_id IS NULL AND room_id IS NOT NULL)
   ```
   *Every bed belongs to EXACTLY ONE: ward or room*

2. **Diagnosis Source** (diagnoses table):
   ```sql
   appointment_id IS NOT NULL OR admission_id IS NOT NULL
   ```
   *Every diagnosis links to EITHER appointment or admission*

### Application-Level
1. **Allergy Cascade** - Updating allergen affects all patient links
2. **Invoice Auto-Update** - Payment triggers status recalculation
3. **Bed Occupancy** - Admission reserves bed (is_occupied = true)
4. **Batch Expiry** - Exclude expired batches from inventory calculations
5. **Token Revocation** - Logout invalidates all refresh tokens
6. **Audit Trail** - All sensitive actions logged immutably

---

## 📈 Scalability Considerations

| Table | Expected Volume | Optimization |
|-------|-----------------|---------------|
| users | 1-10K | Index on email, is_active |
| audit_logs | 1M+ | Partition by timestamp, regular archival |
| vitals_logs | 10M+ | Partition by admission_id, cleanup old records |
| prescription_items | 100K+ | Index on prescription_id, medication_id |
| blood_inventory | <10 | Small reference table, cache in app |
| appointments | 100K+ | Index on patient_id, doctor_id, appointment_date |
| invoices | 100K+ | Index on patient_id, status, created_at |

---

## 🎯 Common Queries

### Active Staff by Department
```sql
SELECT s.* FROM staff_details s
JOIN departments d ON s.department_id = d.id
WHERE d.name = 'Cardiology' AND s.user_id IS NOT NULL;
```

### Pending Blood Requests
```sql
SELECT br.*, p.blood_group FROM blood_requests br
JOIN patient_details p ON br.patient_id = p.id
WHERE br.status = 'pending';
```

### Patient's Current Admission
```sql
SELECT a.* FROM admissions a
WHERE a.patient_id = ? AND a.status = 'admitted'
ORDER BY a.admission_date DESC LIMIT 1;
```

### Available Beds
```sql
SELECT b.* FROM beds b
WHERE b.is_occupied = false
AND b.bed_id IN (
  SELECT w.id FROM wards w
  WHERE w.department_id = ?
);
```

### Unpaid Invoices > 30 Days
```sql
SELECT i.* FROM invoices i
WHERE i.status IN ('unpaid', 'partially_paid')
AND DATE(i.created_at) < DATE_SUB(NOW(), INTERVAL 30 DAY);
```

---

**Last Updated:** 2026-08-13
