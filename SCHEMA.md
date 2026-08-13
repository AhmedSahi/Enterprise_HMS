# Enterprise Hospital Management System - Detailed Schema Documentation

## Table of Contents
1. [Module 1: IAM & Security](#module-1-iam--security)
2. [Module 2: User Profiles & Identity](#module-2-user-profiles--identity)
3. [Module 3: Hospital Infrastructure](#module-3-hospital-infrastructure)
4. [Module 4: Clinical Operations](#module-4-clinical-operations)
5. [Module 5: Pharmacy & Inventory](#module-5-pharmacy--inventory)
6. [Module 6: Billing & Finance](#module-6-billing--finance)
7. [Module 7: Blood Bank](#module-7-blood-bank)
8. [Enums & Type Definitions](#enums--type-definitions)

---

## Module 1: IAM & Security

### Purpose
Manages authentication, authorization, role-based access control (RBAC), session management, and audit trail.

### Tables

#### `users`
**Authentication identity for all system users.**

| Column | Type | Constraints | Notes |
|--------|------|-----------|-------|
| `id` | INTEGER | PRIMARY KEY, AUTO_INCREMENT | Unique user identifier |
| `email` | VARCHAR(255) | UNIQUE, NOT NULL, INDEX | Login credential |
| `hashed_password` | VARCHAR(255) | NOT NULL | bcrypt hashed password |
| `is_active` | BOOLEAN | DEFAULT TRUE, NOT NULL | Soft disable user without deletion |
| `created_at` | DATETIME | DEFAULT NOW(), NOT NULL | Record creation time |
| `updated_at` | DATETIME | DEFAULT NOW(), ON UPDATE NOW() | Last modification time |

**Relationships:**
- One-to-Many: `users` → `refresh_tokens` (multiple sessions per user)
- One-to-Many: `users` → `audit_logs` (activity trail)
- Many-to-Many: `users` ↔ `roles` via `user_roles`
- One-to-One: `users` → `user_profiles` (personal identity)
- One-to-One: `users` → `user_contacts` (contact details)
- One-to-One: `users` → `staff_details` (if staff member)
- One-to-One: `users` → `patient_details` (if patient)
- One-to-Many: `users` → `departments` (as manager)

---

#### `roles`
**Named roles that group permissions together.**

| Column | Type | Constraints | Notes |
|--------|------|-----------|-------|
| `id` | INTEGER | PRIMARY KEY | Unique role identifier |
| `name` | VARCHAR(100) | UNIQUE, NOT NULL, INDEX | Role name (e.g., "admin", "doctor") |
| `description` | TEXT | NULLABLE | Human-readable role description |
| `created_at` | DATETIME | DEFAULT NOW() | Creation timestamp |
| `updated_at` | DATETIME | DEFAULT NOW() | Update timestamp |

**Standard Roles:**
- `admin` - Full system access
- `doctor` - Clinical operations, prescriptions
- `nurse` - Vital signs, patient care
- `receptionist` - Appointments, patient check-in
- `lab_tech` - Lab tests, results
- `pharmacist` - Medication dispensing
- `blood_bank_manager` - Blood inventory
- `patient` - View own records, appointments
- `manager` - Department management

**Relationships:**
- Many-to-Many: `roles` ↔ `users` via `user_roles`
- Many-to-Many: `roles` ↔ `permissions` via `role_permissions`

---

#### `permissions`
**Fine-grained permission codes for authorization.**

| Column | Type | Constraints | Notes |
|--------|------|-----------|-------|
| `id` | INTEGER | PRIMARY KEY | Unique permission identifier |
| `name` | VARCHAR(150) | NOT NULL | Human-readable name |
| `code` | VARCHAR(100) | UNIQUE, NOT NULL, INDEX | Machine-readable code |
| `created_at` | DATETIME | DEFAULT NOW() | Creation timestamp |
| `updated_at` | DATETIME | DEFAULT NOW() | Update timestamp |

**Example Permission Codes:**
- `bloodbank:approve` - Approve blood requests
- `bloodbank:view` - View blood inventory
- `patient:read` - View patient details
- `patient:write` - Edit patient details
- `prescription:create` - Create prescriptions
- `invoice:approve` - Approve invoices
- `audit:view` - Access audit logs

**Relationships:**
- Many-to-Many: `permissions` ↔ `roles` via `role_permissions`

---

#### `user_roles` (Association Table)
**Links users to their assigned roles (many-to-many).**

| Column | Type | Constraints | Notes |
|--------|------|-----------|-------|
| `user_id` | INTEGER | FOREIGN KEY → users.id, PRIMARY KEY | User reference |
| `role_id` | INTEGER | FOREIGN KEY → roles.id, PRIMARY KEY | Role reference |

**Composite Primary Key:** (user_id, role_id)

**Cascade Behavior:** ON DELETE CASCADE (delete user → delete role assignments)

---

#### `role_permissions` (Association Table)
**Links roles to their permissions (many-to-many).**

| Column | Type | Constraints | Notes |
|--------|------|-----------|-------|
| `role_id` | INTEGER | FOREIGN KEY → roles.id, PRIMARY KEY | Role reference |
| `permission_id` | INTEGER | FOREIGN KEY → permissions.id, PRIMARY KEY | Permission reference |

**Composite Primary Key:** (role_id, permission_id)

**Cascade Behavior:** ON DELETE CASCADE

---

#### `refresh_tokens`
**Stores valid refresh tokens for session management and token revocation.**

| Column | Type | Constraints | Notes |
|--------|------|-----------|-------|
| `id` | INTEGER | PRIMARY KEY | Token ID |
| `user_id` | INTEGER | FOREIGN KEY → users.id | User who owns token |
| `token` | VARCHAR(500) | UNIQUE, NOT NULL, INDEX | JWT token value |
| `expires_at` | DATETIME | NOT NULL, WITH TIMEZONE | Expiration time (queryable) |
| `revoked` | BOOLEAN | DEFAULT FALSE, NOT NULL | Soft revoke flag |
| `created_at` | DATETIME | DEFAULT NOW() | Issue timestamp |
| `updated_at` | DATETIME | DEFAULT NOW() | Update timestamp |

**Purpose:**
- Allow token rotation without re-login
- Revoke old tokens without blocking user
- Implement logout functionality
- Track multiple active sessions per user

**Cascade Behavior:** ON DELETE CASCADE (delete user → delete tokens)

---

#### `audit_logs`
**Immutable append-only transaction log for compliance and security auditing.**

| Column | Type | Constraints | Notes |
|--------|------|-----------|-------|
| `id` | INTEGER | PRIMARY KEY | Log entry ID |
| `user_id` | INTEGER | FOREIGN KEY → users.id (nullable) | Who performed action |
| `action` | VARCHAR(255) | NOT NULL | Action description |
| `resource_type` | VARCHAR(100) | NULLABLE | Resource type (e.g., "invoice") |
| `resource_id` | INTEGER | NULLABLE | Resource identifier |
| `ip_address` | VARCHAR(45) | NULLABLE | IPv4 or IPv6 address |
| `status` | VARCHAR(20) | DEFAULT 'success', NOT NULL | success or failure |
| `timestamp` | DATETIME | DEFAULT NOW(), WITH TIMEZONE | Action time |

**Example Audit Entries:**
- Action: `bloodbank:approve`, Resource: `blood_request:123`
- Action: `patient:view`, Resource: `patient_details:456`
- Action: `user:create`, Resource: `user:789`

**Cascade Behavior:** ON DELETE SET NULL (preserve audit history even if user deleted)

---

## Module 2: User Profiles & Identity

### Purpose
Manages user identity, contact information, staff and patient specific details, allergies, and medical history.

### Tables

#### `user_profiles`
**Personal identity information shared by all users.**

| Column | Type | Constraints | Notes |
|--------|------|-----------|-------|
| `id` | INTEGER | PRIMARY KEY | Profile ID |
| `user_id` | INTEGER | FOREIGN KEY → users.id, UNIQUE, NOT NULL | Linked user (1:1) |
| `first_name` | VARCHAR(100) | NOT NULL | First name |
| `last_name` | VARCHAR(100) | NOT NULL | Last name |
| `gender` | ENUM | NOT NULL | male, female, other |
| `dob` | DATE | NOT NULL | Date of birth |
| `cnic` | VARCHAR(20) | UNIQUE, NULLABLE | CNIC/ID number (e.g., Pakistan) |
| `created_at` | DATETIME | DEFAULT NOW() | Creation timestamp |
| `updated_at` | DATETIME | DEFAULT NOW() | Update timestamp |

**Cascade Behavior:** ON DELETE CASCADE (delete user → delete profile)

---

#### `user_contacts`
**Contact details for all users (staff and patients).**

| Column | Type | Constraints | Notes |
|--------|------|-----------|-------|
| `id` | INTEGER | PRIMARY KEY | Contact ID |
| `user_id` | INTEGER | FOREIGN KEY → users.id, UNIQUE, NOT NULL | Linked user (1:1) |
| `primary_phone` | VARCHAR(20) | NOT NULL | Main contact number |
| `secondary_phone` | VARCHAR(20) | NULLABLE | Alternate phone |
| `address` | TEXT | NULLABLE | Street address |
| `emergency_name` | VARCHAR(150) | NULLABLE | Emergency contact name |
| `emergency_phone` | VARCHAR(20) | NULLABLE | Emergency contact number |
| `created_at` | DATETIME | DEFAULT NOW() | Creation timestamp |
| `updated_at` | DATETIME | DEFAULT NOW() | Update timestamp |

**Cascade Behavior:** ON DELETE CASCADE

---

#### `staff_details`
**Employment and role-specific metadata for staff members.**

| Column | Type | Constraints | Notes |
|--------|------|-----------|-------|
| `id` | INTEGER | PRIMARY KEY | Staff detail ID |
| `user_id` | INTEGER | FOREIGN KEY → users.id, UNIQUE, NOT NULL | Linked user (1:1) |
| `department_id` | INTEGER | FOREIGN KEY → departments.id (nullable), ON DELETE SET NULL | Department assignment |
| `employee_code` | VARCHAR(50) | UNIQUE, NOT NULL | Unique employee ID |
| `staff_type` | ENUM | NOT NULL | doctor, nurse, receptionist, lab_tech, pharmacist, admin |
| `specialization` | VARCHAR(150) | NULLABLE | Doctor specialization (e.g., "Cardiology") |
| `license_number` | VARCHAR(100) | UNIQUE, NULLABLE | Medical license (doctors only) |
| `consultation_fee` | NUMERIC(10,2) | NULLABLE | Hourly rate for doctors |
| `created_at` | DATETIME | DEFAULT NOW() | Creation timestamp |
| `updated_at` | DATETIME | DEFAULT NOW() | Update timestamp |

**Cascade Behavior:** ON DELETE CASCADE

**Relationships:**
- One-to-Many: `staff_details` → `doctor_schedules` (availability slots)
- Many-to-One: `staff_details` → `departments`

---

#### `patient_details`
**Hospital-specific patient metadata and medical records.**

| Column | Type | Constraints | Notes |
|--------|------|-----------|-------|
| `id` | INTEGER | PRIMARY KEY | Patient detail ID |
| `user_id` | INTEGER | FOREIGN KEY → users.id, UNIQUE, NOT NULL | Linked user (1:1) |
| `patient_code` | VARCHAR(50) | UNIQUE, NOT NULL | Medical Record Number (MRN) |
| `blood_group` | VARCHAR(5) | NOT NULL | A, B, AB, O (with +/- qualifier) |
| `created_at` | DATETIME | DEFAULT NOW() | Creation timestamp |
| `updated_at` | DATETIME | DEFAULT NOW() | Update timestamp |

**Cascade Behavior:** ON DELETE CASCADE

**Relationships:**
- One-to-Many: `patient_details` → `allergies`
- One-to-Many: `patient_details` → `medical_history`

---

#### `allergens`
**Master list of known allergens, reusable across all patients.**

| Column | Type | Constraints | Notes |
|--------|------|-----------|-------|
| `id` | INTEGER | PRIMARY KEY | Allergen ID |
| `name` | VARCHAR(150) | UNIQUE, NOT NULL | Allergen name (e.g., "Penicillin") |
| `category` | ENUM | NOT NULL | drug, food, environmental |
| `created_at` | DATETIME | DEFAULT NOW() | Creation timestamp |
| `updated_at` | DATETIME | DEFAULT NOW() | Update timestamp |

**Purpose:** Normalize allergens so updates propagate to all patient records

---

#### `patient_allergies`
**Links patients to allergens with severity levels.**

| Column | Type | Constraints | Notes |
|--------|------|-----------|-------|
| `id` | INTEGER | PRIMARY KEY | Link ID |
| `patient_id` | INTEGER | FOREIGN KEY → patient_details.id, NOT NULL | Patient reference |
| `allergen_id` | INTEGER | FOREIGN KEY → allergens.id, NOT NULL | Allergen reference |
| `severity` | ENUM | NOT NULL | mild, moderate, severe |
| `reaction_notes` | TEXT | NULLABLE | Detailed reaction description |
| `created_at` | DATETIME | DEFAULT NOW() | Creation timestamp |
| `updated_at` | DATETIME | DEFAULT NOW() | Update timestamp |

**Cascade Behavior:** ON DELETE CASCADE for both foreign keys

**Purpose:** Track patient-specific allergen reactions with severity

---

#### `patient_medical_history`
**Chronic and past medical conditions for a patient.**

| Column | Type | Constraints | Notes |
|--------|------|-----------|-------|
| `id` | INTEGER | PRIMARY KEY | History record ID |
| `patient_id` | INTEGER | FOREIGN KEY → patient_details.id, NOT NULL | Patient reference |
| `condition` | VARCHAR(255) | NOT NULL | Medical condition name |
| `onset_date` | DATE | NULLABLE | When condition started |
| `status` | ENUM | NOT NULL | active, resolved, chronic |
| `notes` | TEXT | NULLABLE | Additional details |
| `created_at` | DATETIME | DEFAULT NOW() | Creation timestamp |
| `updated_at` | DATETIME | DEFAULT NOW() | Update timestamp |

**Cascade Behavior:** ON DELETE CASCADE

**Purpose:** Track patient medical background independent of visits

---

## Module 3: Hospital Infrastructure

### Purpose
Manages physical hospital structure: departments, wards, rooms, beds, and operation theaters.

### Tables

#### `departments`
**Organizational units within the hospital, each with a manager.**

| Column | Type | Constraints | Notes |
|--------|------|-----------|-------|
| `id` | INTEGER | PRIMARY KEY | Department ID |
| `name` | VARCHAR(150) | UNIQUE, NOT NULL | Department name |
| `manager_id` | INTEGER | FOREIGN KEY → users.id (nullable), ON DELETE SET NULL | Department head |
| `created_at` | DATETIME | DEFAULT NOW() | Creation timestamp |
| `updated_at` | DATETIME | DEFAULT NOW() | Update timestamp |

**Example Departments:**
- Cardiology
- Emergency
- Orthopedics
- Pediatrics
- Administration

**Relationships:**
- One-to-Many: `departments` → `staff_details` (employees)
- One-to-Many: `departments` → `wards` (patient halls)
- One-to-Many: `departments` → `operation_theaters` (surgery suites)

---

#### `wards`
**Shared patient halls within a department.**

| Column | Type | Constraints | Notes |
|--------|------|-----------|-------|
| `id` | INTEGER | PRIMARY KEY | Ward ID |
| `department_id` | INTEGER | FOREIGN KEY → departments.id, NOT NULL | Parent department |
| `name` | VARCHAR(150) | NOT NULL | Ward name (e.g., "Ward A") |
| `ward_type` | VARCHAR(50) | NOT NULL | general, icu, isolation, pediatric |
| `total_capacity` | INTEGER | NOT NULL | Total beds in ward |
| `created_at` | DATETIME | DEFAULT NOW() | Creation timestamp |
| `updated_at` | DATETIME | DEFAULT NOW() | Update timestamp |

**Cascade Behavior:** ON DELETE CASCADE

**Relationships:**
- One-to-Many: `wards` → `beds` (physical beds)

---

#### `rooms`
**Private or semi-private patient rooms, independent of wards.**

| Column | Type | Constraints | Notes |
|--------|------|-----------|-------|
| `id` | INTEGER | PRIMARY KEY | Room ID |
| `room_number` | VARCHAR(20) | UNIQUE, NOT NULL | Room identifier |
| `room_type` | VARCHAR(50) | NOT NULL | private, semi_private |
| `floor` | VARCHAR(20) | NULLABLE | Floor number/name |
| `daily_rate` | NUMERIC(10,2) | NOT NULL | Accommodation cost per day |
| `status` | ENUM | DEFAULT 'available', NOT NULL | available, occupied, maintenance |
| `created_at` | DATETIME | DEFAULT NOW() | Creation timestamp |
| `updated_at` | DATETIME | DEFAULT NOW() | Update timestamp |

**Purpose:** Premium accommodation outside regular ward system

**Relationships:**
- One-to-Many: `rooms` → `beds`

---

#### `beds`
**Physical patient beds, either in a ward or private room (mutually exclusive).**

| Column | Type | Constraints | Notes |
|--------|------|-----------|-------|
| `id` | INTEGER | PRIMARY KEY | Bed ID |
| `bed_number` | VARCHAR(20) | NOT NULL | Bed identifier |
| `ward_id` | INTEGER | FOREIGN KEY → wards.id (nullable), ON DELETE CASCADE | Ward location |
| `room_id` | INTEGER | FOREIGN KEY → rooms.id (nullable), ON DELETE CASCADE | Room location |
| `is_occupied` | BOOLEAN | DEFAULT FALSE, NOT NULL | Occupancy flag |
| `created_at` | DATETIME | DEFAULT NOW() | Creation timestamp |
| `updated_at` | DATETIME | DEFAULT NOW() | Update timestamp |

**CHECK Constraint:**
```sql
(ward_id IS NOT NULL AND room_id IS NULL) OR (ward_id IS NULL AND room_id IS NOT NULL)
```
*Every bed must belong to EXACTLY ONE location: either a ward or a room, never both or neither.*

**Purpose:** Flexible bed allocation across ward and private room systems

**Relationships:**
- One-to-Many: `beds` → `admissions` (current occupant)

---

#### `bed_transfers`
**History of patient movements between beds during a single admission.**

| Column | Type | Constraints | Notes |
|--------|------|-----------|-------|
| `id` | INTEGER | PRIMARY KEY | Transfer ID |
| `admission_id` | INTEGER | FOREIGN KEY → admissions.id, NOT NULL | Which admission |
| `from_bed_id` | INTEGER | FOREIGN KEY → beds.id (nullable), ON DELETE SET NULL | Source bed |
| `to_bed_id` | INTEGER | FOREIGN KEY → beds.id, NOT NULL | Destination bed |
| `transferred_at` | DATETIME | WITH TIMEZONE, NOT NULL | Transfer timestamp |
| `reason` | TEXT | NULLABLE | Why patient was moved |
| `created_at` | DATETIME | DEFAULT NOW() | Record creation time |
| `updated_at` | DATETIME | DEFAULT NOW() | Update timestamp |

**Cascade Behavior:** ON DELETE CASCADE (admission deleted → transfer deleted)

**Purpose:** Audit trail of patient bed movements

---

#### `operation_theaters`
**Surgery suites for scheduled surgical procedures.**

| Column | Type | Constraints | Notes |
|--------|------|-----------|-------|
| `id` | INTEGER | PRIMARY KEY | OT ID |
| `name_or_code` | VARCHAR(50) | UNIQUE, NOT NULL | OT identifier (e.g., "OT-1") |
| `department_id` | INTEGER | FOREIGN KEY → departments.id (nullable), ON DELETE SET NULL | Parent department |
| `floor` | VARCHAR(20) | NULLABLE | Floor location |
| `status` | ENUM | DEFAULT 'available', NOT NULL | available, in_use, maintenance |
| `created_at` | DATETIME | DEFAULT NOW() | Creation timestamp |
| `updated_at` | DATETIME | DEFAULT NOW() | Update timestamp |

**Relationships:**
- One-to-Many: `operation_theaters` → `ot_schedules`

---

## Module 4: Clinical Operations

### Purpose
Manages appointments, admissions, diagnoses, prescriptions, vital signs monitoring, and surgical scheduling.

### Tables

#### `doctor_schedules`
**Weekly recurring availability slots for doctor consultations.**

| Column | Type | Constraints | Notes |
|--------|------|-----------|-------|
| `id` | INTEGER | PRIMARY KEY | Schedule ID |
| `doctor_id` | INTEGER | FOREIGN KEY → staff_details.id, NOT NULL | Staff member (must be doctor) |
| `day_of_week` | INTEGER | NOT NULL | 0=Monday ... 6=Sunday |
| `start_time` | TIME | NOT NULL | Shift start time |
| `end_time` | TIME | NOT NULL | Shift end time |
| `slot_duration_minutes` | INTEGER | DEFAULT 30, NOT NULL | Appointment duration |
| `created_at` | DATETIME | DEFAULT NOW() | Creation timestamp |
| `updated_at` | DATETIME | DEFAULT NOW() | Update timestamp |

**Example:** Doctor available Monday 9:00-17:00 with 30-minute slots = 16 slots/day

**Purpose:** Generate available appointment slots for booking

**Cascade Behavior:** ON DELETE CASCADE (delete doctor → delete schedules)

---

#### `appointments`
**Out-patient clinic (OPD) consultation bookings.**

| Column | Type | Constraints | Notes |
|--------|------|-----------|-------|
| `id` | INTEGER | PRIMARY KEY | Appointment ID |
| `patient_id` | INTEGER | FOREIGN KEY → patient_details.id, NOT NULL | Patient |
| `doctor_id` | INTEGER | FOREIGN KEY → staff_details.id, NOT NULL | Treating doctor |
| `appointment_date` | DATE | NOT NULL | Consultation date |
| `appointment_time` | TIME | NOT NULL | Consultation time |
| `duration_minutes` | INTEGER | DEFAULT 30, NOT NULL | Appointment length |
| `status` | ENUM | DEFAULT 'pending', NOT NULL | pending, confirmed, completed, cancelled |
| `created_at` | DATETIME | DEFAULT NOW() | Creation timestamp |
| `updated_at` | DATETIME | DEFAULT NOW() | Update timestamp |

**Cascade Behavior:** ON DELETE CASCADE

**Relationships:**
- One-to-Many: `appointments` → `diagnoses` (may have multiple diagnoses)
- One-to-Many: `appointments` → `prescriptions`
- One-to-Many: `appointments` → `invoices`

---

#### `admissions`
**In-patient (IPD) stays with bed assignment and duration tracking.**

| Column | Type | Constraints | Notes |
|--------|------|-----------|-------|
| `id` | INTEGER | PRIMARY KEY | Admission ID |
| `patient_id` | INTEGER | FOREIGN KEY → patient_details.id, NOT NULL | Patient |
| `bed_id` | INTEGER | FOREIGN KEY → beds.id, NOT NULL (RESTRICT) | Assigned bed |
| `admitted_by_doctor_id` | INTEGER | FOREIGN KEY → staff_details.id (nullable), ON DELETE SET NULL | Admitting doctor |
| `admission_date` | DATETIME | WITH TIMEZONE, NOT NULL | Check-in time |
| `discharge_date` | DATETIME | WITH TIMEZONE (nullable) | Check-out time |
| `status` | ENUM | DEFAULT 'admitted', NOT NULL | admitted, discharged, transferred |
| `created_at` | DATETIME | DEFAULT NOW() | Creation timestamp |
| `updated_at` | DATETIME | DEFAULT NOW() | Update timestamp |

**Cascade Behavior:** ON DELETE CASCADE for most FK except bed (RESTRICT)

**Relationships:**
- One-to-Many: `admissions` → `bed_transfers` (movement history)
- One-to-One: `admissions` → `discharge_summary`
- One-to-Many: `admissions` → `vitals_logs`
- One-to-Many: `admissions` → `diagnoses`
- One-to-Many: `admissions` → `prescriptions`
- One-to-Many: `admissions` → `invoices`

---

#### `discharge_summaries`
**Clinical summary written at the end of an admission.**

| Column | Type | Constraints | Notes |
|--------|------|-----------|-------|
| `id` | INTEGER | PRIMARY KEY | Summary ID |
| `admission_id` | INTEGER | FOREIGN KEY → admissions.id, UNIQUE, NOT NULL | Linked admission (1:1) |
| `final_diagnosis` | TEXT | NOT NULL | Primary diagnosis at discharge |
| `treatment_given` | TEXT | NOT NULL | Procedures and treatments provided |
| `follow_up_instructions` | TEXT | NULLABLE | Post-discharge care instructions |
| `discharged_by_doctor_id` | INTEGER | FOREIGN KEY → staff_details.id (nullable), ON DELETE SET NULL | Discharging physician |
| `created_at` | DATETIME | DEFAULT NOW() | Creation timestamp |
| `updated_at` | DATETIME | DEFAULT NOW() | Update timestamp |

**Cascade Behavior:** ON DELETE CASCADE (admission deleted → summary deleted)

**Purpose:** Clinical record of hospitalization outcome

---

#### `vitals_logs`
**Single vital signs measurement record.**

| Column | Type | Constraints | Notes |
|--------|------|-----------|-------|
| `id` | INTEGER | PRIMARY KEY | Log ID |
| `patient_id` | INTEGER | FOREIGN KEY → patient_details.id, NOT NULL | Which patient |
| `admission_id` | INTEGER | FOREIGN KEY → admissions.id (nullable) | IPD admission (if any) |
| `recorded_by` | INTEGER | FOREIGN KEY → users.id (nullable), ON DELETE SET NULL | Nurse/staff member |
| `bp_systolic` | INTEGER (nullable) | Optional | Systolic blood pressure (mmHg) |
| `bp_diastolic` | INTEGER (nullable) | Optional | Diastolic blood pressure (mmHg) |
| `temperature` | NUMERIC(4,1) (nullable) | Optional | Body temperature (Celsius) |
| `pulse` | INTEGER (nullable) | Optional | Heart rate (bpm) |
| `spo2` | INTEGER (nullable) | Optional | Blood oxygen saturation (%) |
| `recorded_at` | DATETIME | WITH TIMEZONE, NOT NULL | Measurement timestamp |
| `created_at` | DATETIME | DEFAULT NOW() | Record creation time |
| `updated_at` | DATETIME | DEFAULT NOW() | Update timestamp |

**Cascade Behavior:** ON DELETE CASCADE

**Purpose:** Continuous monitoring of patient health during IPD stay

---

#### `ot_schedules`
**Scheduled surgical procedures in operation theaters.**

| Column | Type | Constraints | Notes |
|--------|------|-----------|-------|
| `id` | INTEGER | PRIMARY KEY | Schedule ID |
| `ot_id` | INTEGER | FOREIGN KEY → operation_theaters.id, NOT NULL | Which OT |
| `patient_id` | INTEGER | FOREIGN KEY → patient_details.id, NOT NULL | Patient to be operated |
| `lead_surgeon_id` | INTEGER | FOREIGN KEY → staff_details.id (nullable), ON DELETE SET NULL | Primary surgeon |
| `scheduled_start` | DATETIME | WITH TIMEZONE, NOT NULL | Surgery start time |
| `scheduled_end` | DATETIME | WITH TIMEZONE, NOT NULL | Surgery end time |
| `status` | ENUM | DEFAULT 'scheduled', NOT NULL | scheduled, in_progress, completed, cancelled |
| `created_at` | DATETIME | DEFAULT NOW() | Creation timestamp |
| `updated_at` | DATETIME | DEFAULT NOW() | Update timestamp |

**Cascade Behavior:** ON DELETE CASCADE

**Relationships:**
- One-to-Many: `ot_schedules` → `ot_team_members` (surgical team)

---

#### `ot_team_members`
**Staff assisting in a scheduled surgery.**

| Column | Type | Constraints | Notes |
|--------|------|-----------|-------|
| `id` | INTEGER | PRIMARY KEY | Team member ID |
| `ot_schedule_id` | INTEGER | FOREIGN KEY → ot_schedules.id, NOT NULL | Which surgery |
| `staff_id` | INTEGER | FOREIGN KEY → staff_details.id, NOT NULL | Staff member |
| `role_in_surgery` | ENUM | NOT NULL | anesthetist, assistant_surgeon, scrub_nurse |
| `created_at` | DATETIME | DEFAULT NOW() | Creation timestamp |
| `updated_at` | DATETIME | DEFAULT NOW() | Update timestamp |

**Cascade Behavior:** ON DELETE CASCADE

**Purpose:** Track complete surgical team composition

---

#### `diagnoses`
**ICD-coded diagnoses tied to either OPD visit or IPD stay.**

| Column | Type | Constraints | Notes |
|--------|------|-----------|-------|
| `id` | INTEGER | PRIMARY KEY | Diagnosis ID |
| `appointment_id` | INTEGER | FOREIGN KEY → appointments.id (nullable), ON DELETE CASCADE | OPD visit |
| `admission_id` | INTEGER | FOREIGN KEY → admissions.id (nullable), ON DELETE CASCADE | IPD stay |
| `icd_code` | VARCHAR(20) | NOT NULL | ICD-10/ICD-11 code |
| `description` | VARCHAR(255) | NOT NULL | Diagnosis description |
| `created_at` | DATETIME | DEFAULT NOW() | Creation timestamp |
| `updated_at` | DATETIME | DEFAULT NOW() | Update timestamp |

**CHECK Constraint:**
```sql
appointment_id IS NOT NULL OR admission_id IS NOT NULL
```
*Every diagnosis must link to EITHER an appointment OR an admission.*

**Purpose:** Clinical diagnosis records with standardized coding

---

#### `prescriptions`
**Medicine prescriptions issued during appointments or admissions.**

| Column | Type | Constraints | Notes |
|--------|------|-----------|-------|
| `id` | INTEGER | PRIMARY KEY | Prescription ID |
| `patient_id` | INTEGER | FOREIGN KEY → patient_details.id, NOT NULL | Patient |
| `appointment_id` | INTEGER | FOREIGN KEY → appointments.id (nullable), ON DELETE SET NULL | From OPD visit |
| `admission_id` | INTEGER | FOREIGN KEY → admissions.id (nullable), ON DELETE SET NULL | From IPD stay |
| `prescribed_by` | INTEGER | FOREIGN KEY → staff_details.id (nullable), ON DELETE SET NULL | Prescribing doctor |
| `status` | ENUM | DEFAULT 'active', NOT NULL | active, completed, cancelled |
| `created_at` | DATETIME | DEFAULT NOW() | Creation timestamp |
| `updated_at` | DATETIME | DEFAULT NOW() | Update timestamp |

**Cascade Behavior:** ON DELETE CASCADE

**Relationships:**
- One-to-Many: `prescriptions` → `prescription_items` (individual medicines)

---

#### `prescription_items`
**Individual medicines within a prescription.**

| Column | Type | Constraints | Notes |
|--------|------|-----------|-------|
| `id` | INTEGER | PRIMARY KEY | Item ID |
| `prescription_id` | INTEGER | FOREIGN KEY → prescriptions.id, NOT NULL | Parent prescription |
| `medication_id` | INTEGER | FOREIGN KEY → medications.id, NOT NULL | Drug |
| `quantity` | INTEGER | NOT NULL | Number of units (tablets, bottles, etc.) |
| `dosage` | VARCHAR(100) | NOT NULL | Dosage instruction (e.g., "500mg twice daily") |
| `duration_days` | INTEGER | NOT NULL | How long to take medicine |
| `instructions` | TEXT | NULLABLE | Special instructions (with food, etc.) |
| `created_at` | DATETIME | DEFAULT NOW() | Creation timestamp |
| `updated_at` | DATETIME | DEFAULT NOW() | Update timestamp |

**Cascade Behavior:** ON DELETE CASCADE

**Purpose:** Detailed medication instructions for patient

---

## Module 5: Pharmacy & Inventory

### Purpose
Manages drug catalog and physical medication batches with expiry tracking.

### Tables

#### `medications`
**Drug catalog (master list, not inventory).**

| Column | Type | Constraints | Notes |
|--------|------|-----------|-------|
| `id` | INTEGER | PRIMARY KEY | Medication ID |
| `name` | VARCHAR(200) | NOT NULL | Brand name |
| `generic_name` | VARCHAR(200) | NULLABLE | Generic/chemical name |
| `dosage_form` | VARCHAR(50) | NOT NULL | tablet, syrup, injection, cream, etc. |
| `strength` | VARCHAR(50) | NOT NULL | e.g., "500mg", "10%", "200IU/mL" |
| `unit_price` | NUMERIC(10,2) | NOT NULL | Cost per unit |
| `created_at` | DATETIME | DEFAULT NOW() | Creation timestamp |
| `updated_at` | DATETIME | DEFAULT NOW() | Update timestamp |

**Relationships:**
- One-to-Many: `medications` → `medication_batches` (physical stock)
- One-to-Many: `medications` → `prescription_items` (usage in prescriptions)

---

#### `medication_batches`
**Physical batches of stock with expiry tracking.**

| Column | Type | Constraints | Notes |
|--------|------|-----------|-------|
| `id` | INTEGER | PRIMARY KEY | Batch ID |
| `medication_id` | INTEGER | FOREIGN KEY → medications.id, NOT NULL | Which drug |
| `batch_number` | VARCHAR(100) | NOT NULL | Manufacturer batch code |
| `expiry_date` | DATE | NOT NULL | When batch expires |
| `quantity_available` | INTEGER | NOT NULL, DEFAULT 0 | Current stock level |
| `supplier_name` | VARCHAR(200) | NULLABLE | Supplier/distributor |
| `created_at` | DATETIME | DEFAULT NOW() | Creation timestamp |
| `updated_at` | DATETIME | DEFAULT NOW() | Update timestamp |

**UNIQUE Constraint:** (medication_id, batch_number)

**Cascade Behavior:** ON DELETE CASCADE

**Purpose:**
- Track individual batches separately (different expiry dates)
- Query available stock excluding expired batches
- Support batch recalls if needed

---

## Module 6: Billing & Finance

### Purpose
Manages patient invoices, itemized charges, payments, and insurance.

### Tables

#### `invoices`
**Patient billing record.**

| Column | Type | Constraints | Notes |
|--------|------|-----------|-------|
| `id` | INTEGER | PRIMARY KEY | Invoice ID |
| `patient_id` | INTEGER | FOREIGN KEY → patient_details.id, NOT NULL | Patient being billed |
| `appointment_id` | INTEGER | FOREIGN KEY → appointments.id (nullable), ON DELETE SET NULL | From OPD visit |
| `admission_id` | INTEGER | FOREIGN KEY → admissions.id (nullable), ON DELETE SET NULL | From IPD stay |
| `total_amount` | NUMERIC(12,2) | NOT NULL, DEFAULT 0 | Total bill amount |
| `paid_amount` | NUMERIC(12,2) | NOT NULL, DEFAULT 0 | Amount paid so far |
| `status` | ENUM | DEFAULT 'unpaid', NOT NULL | unpaid, partially_paid, paid, cancelled |
| `created_at` | DATETIME | DEFAULT NOW() | Creation timestamp |
| `updated_at` | DATETIME | DEFAULT NOW() | Update timestamp |

**Relationships:**
- One-to-Many: `invoices` → `invoice_items` (line items)
- One-to-Many: `invoices` → `payments` (payment history)

**Note:** `total_amount` and `paid_amount` are running totals; breakdown lives in `invoice_items` and `payments`

---

#### `invoice_items`
**Individual line item on an invoice.**

| Column | Type | Constraints | Notes |
|--------|------|-----------|-------|
| `id` | INTEGER | PRIMARY KEY | Item ID |
| `invoice_id` | INTEGER | FOREIGN KEY → invoices.id, NOT NULL | Parent invoice |
| `item_type` | ENUM | NOT NULL | consultation, room, medicine, lab, ot, other |
| `description` | VARCHAR(255) | NOT NULL | Item description |
| `quantity` | INTEGER | NOT NULL, DEFAULT 1 | Units |
| `unit_price` | NUMERIC(10,2) | NOT NULL | Price per unit |
| `amount` | NUMERIC(12,2) | NOT NULL | quantity × unit_price (denormalized for audit) |
| `created_at` | DATETIME | DEFAULT NOW() | Creation timestamp |
| `updated_at` | DATETIME | DEFAULT NOW() | Update timestamp |

**Cascade Behavior:** ON DELETE CASCADE

**Purpose:** Itemized breakdown for transparency and auditing

---

#### `payments`
**Payment transaction against an invoice.**

| Column | Type | Constraints | Notes |
|--------|------|-----------|-------|
| `id` | INTEGER | PRIMARY KEY | Payment ID |
| `invoice_id` | INTEGER | FOREIGN KEY → invoices.id, NOT NULL | Invoice being paid |
| `amount_paid` | NUMERIC(12,2) | NOT NULL | Payment amount |
| `payment_method` | ENUM | NOT NULL | cash, card, bank_transfer, insurance |
| `processed_by` | INTEGER | FOREIGN KEY → users.id (nullable), ON DELETE SET NULL | Staff who processed |
| `transaction_date` | DATETIME | WITH TIMEZONE, NOT NULL | Payment timestamp |
| `created_at` | DATETIME | DEFAULT NOW() | Creation timestamp |
| `updated_at` | DATETIME | DEFAULT NOW() | Update timestamp |

**Cascade Behavior:** ON DELETE CASCADE

**Purpose:**
- Support multiple partial payments
- Track payment method for reconciliation
- Audit trail of who processed payment

---

#### `insurance_providers`
**TPA / Insurance companies.**

| Column | Type | Constraints | Notes |
|--------|------|-----------|-------|
| `id` | INTEGER | PRIMARY KEY | Provider ID |
| `name` | VARCHAR(200) | UNIQUE, NOT NULL | Insurance company name |
| `contact_info` | VARCHAR(255) | NULLABLE | Phone, email, website |
| `created_at` | DATETIME | DEFAULT NOW() | Creation timestamp |
| `updated_at` | DATETIME | DEFAULT NOW() | Update timestamp |

**Relationships:**
- One-to-Many: `insurance_providers` → `patient_insurance`

---

#### `patient_insurance`
**Patient's active insurance policies.**

| Column | Type | Constraints | Notes |
|--------|------|-----------|-------|
| `id` | INTEGER | PRIMARY KEY | Policy ID |
| `patient_id` | INTEGER | FOREIGN KEY → patient_details.id, NOT NULL | Patient |
| `provider_id` | INTEGER | FOREIGN KEY → insurance_providers.id, NOT NULL | Insurance provider |
| `policy_number` | VARCHAR(100) | NOT NULL | Policy ID |
| `coverage_details` | VARCHAR(500) | NULLABLE | Coverage limitations |
| `created_at` | DATETIME | DEFAULT NOW() | Creation timestamp |
| `updated_at` | DATETIME | DEFAULT NOW() | Update timestamp |

**Cascade Behavior:** ON DELETE CASCADE for both FK

**Purpose:** Track patient insurance coverage

---

## Module 7: Blood Bank

### Purpose
Manages blood inventory and patient blood requests with approval workflow.

### Tables

#### `blood_inventory`
**Current blood stock by blood group.**

| Column | Type | Constraints | Notes |
|--------|------|-----------|-------|
| `id` | INTEGER | PRIMARY KEY | Inventory ID |
| `blood_group` | VARCHAR(5) | UNIQUE, NOT NULL | A, B, AB, O with +/- |
| `available_units` | INTEGER | NOT NULL, DEFAULT 0 | Current stock |
| `last_updated` | DATETIME | WITH TIMEZONE (nullable) | Last modification time |
| `created_at` | DATETIME | DEFAULT NOW() | Creation timestamp |
| `updated_at` | DATETIME | DEFAULT NOW() | Update timestamp |

**Purpose:** One record per blood group for real-time availability

---

#### `blood_requests`
**Patient blood request with approval workflow.**

| Column | Type | Constraints | Notes |
|--------|------|-----------|-------|
| `id` | INTEGER | PRIMARY KEY | Request ID |
| `patient_id` | INTEGER | FOREIGN KEY → patient_details.id, NOT NULL | Patient requesting blood |
| `requested_by_doctor_id` | INTEGER | FOREIGN KEY → staff_details.id (nullable), ON DELETE SET NULL | Requesting doctor |
| `blood_group` | VARCHAR(5) | NOT NULL | A, B, AB, O with +/- |
| `units_required` | INTEGER | NOT NULL | Number of units needed |
| `status` | ENUM | DEFAULT 'pending', NOT NULL | pending, approved, rejected |
| `processed_by` | INTEGER | FOREIGN KEY → users.id (nullable), ON DELETE SET NULL | Blood bank staff |
| `created_at` | DATETIME | DEFAULT NOW() | Creation timestamp |
| `updated_at` | DATETIME | DEFAULT NOW() | Update timestamp |

**Cascade Behavior:** ON DELETE CASCADE

**Workflow:**
1. Doctor creates request (PENDING)
2. Blood bank manager reviews (APPROVED/REJECTED)
3. If approved, update `blood_inventory` (decrement available units)

---

## Enums & Type Definitions

### Gender
```python
MALE = "male"
FEMALE = "female"
OTHER = "other"
```

### Staff Type
```python
DOCTOR = "doctor"
NURSE = "nurse"
RECEPTIONIST = "receptionist"
LAB_TECH = "lab_tech"
PHARMACIST = "pharmacist"
ADMIN = "admin"
```

### Allergen Category
```python
DRUG = "drug"
FOOD = "food"
ENVIRONMENTAL = "environmental"
```

### Allergy Severity
```python
MILD = "mild"
MODERATE = "moderate"
SEVERE = "severe"
```

### Medical History Status
```python
ACTIVE = "active"
RESOLVED = "resolved"
CHRONIC = "chronic"
```

### Appointment Status
```python
PENDING = "pending"
CONFIRMED = "confirmed"
COMPLETED = "completed"
CANCELLED = "cancelled"
```

### Admission Status
```python
ADMITTED = "admitted"
DISCHARGED = "discharged"
TRANSFERRED = "transferred"
```

### OT Schedule Status
```python
SCHEDULED = "scheduled"
IN_PROGRESS = "in_progress"
COMPLETED = "completed"
CANCELLED = "cancelled"
```

### OT Role
```python
ANESTHETIST = "anesthetist"
ASSISTANT_SURGEON = "assistant_surgeon"
SCRUB_NURSE = "scrub_nurse"
```

### Room Status
```python
AVAILABLE = "available"
OCCUPIED = "occupied"
MAINTENANCE = "maintenance"
```

### OT Status
```python
AVAILABLE = "available"
IN_USE = "in_use"
MAINTENANCE = "maintenance"
```

### Invoice Item Type
```python
CONSULTATION = "consultation"
ROOM = "room"
MEDICINE = "medicine"
LAB = "lab"
OT = "ot"
OTHER = "other"
```

### Invoice Status
```python
UNPAID = "unpaid"
PARTIALLY_PAID = "partially_paid"
PAID = "paid"
CANCELLED = "cancelled"
```

### Payment Method
```python
CASH = "cash"
CARD = "card"
BANK_TRANSFER = "bank_transfer"
INSURANCE = "insurance"
```

### Blood Request Status
```python
PENDING = "pending"
APPROVED = "approved"
REJECTED = "rejected"
```

---

## Summary Statistics

| Category | Count |
|----------|-------|
| **Total Tables** | 37 |
| **Core IAM Tables** | 7 |
| **Profile Tables** | 7 |
| **Infrastructure Tables** | 6 |
| **Clinical Tables** | 9 |
| **Pharmacy Tables** | 2 |
| **Billing Tables** | 5 |
| **Blood Bank Tables** | 2 |
| **Association Tables** | 2 |
| **Enum Types** | 15+ |
| **Check Constraints** | 2 |
| **Unique Constraints** | 15+ |

---

**Last Updated:** 2026-08-13
