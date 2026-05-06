# Required Documents for Provider Credibility System

To accurately predict credibility score and level, the system expects the following documents from providers:

## 1️⃣ Identity Document

**Purpose**: Verify the provider's real identity.

**Accepted Formats:**
- PDF
- PNG / JPG (clear photo scan)

**Required Details:**
- Full Name
- Date of Birth
- ID Number (National Identity Card / Driving License)

**Example Contents:**
```
National Identity Card
Name: John Doe
DOB: 01-01-1990
ID: 123456789V
```

**Feature Extracted:**
- `identity_verified` → 1 if valid, else 0

---

## 2️⃣ Certifications

**Purpose**: Validate professional qualifications and skill levels.

**Accepted Formats:**
- PDF
- PNG / JPG

**Required Details:**
- Certificate Title / Level (NVQ Level 3 / NVQ Level 4 / Technical College / Vocational)
- Service Type (e.g., Electrician, Plumber)
- Issuing Institution
- Issue Date

**Example Contents:**
```
NVQ Level 4 Certificate
Service: Electrician
Institution: Technical College ABC
Date: 2021
```

**Features Extracted:**
- `certification_count` → Number of certificates uploaded
- `highest_cert_level` → Highest certificate attained
- `cert_issuer_reputation` → Credibility of institution (0–1)

---

## 3️⃣ Business Registration Certificate

**Purpose**: Verify legal registration of provider as self-employed or company.

**Accepted Formats:**
- PDF
- PNG / JPG

**Required Details:**
- Company Name
- Owner Name
- Registration Number

**Example Contents:**
```
Business Registration Certificate
Company Name: ABC Services Pvt Ltd
Owner: John Doe
Registration Number: 1234
```

**Feature Extracted:**
- `business_registered` → 1 if valid, else 0

---

## 4️⃣ Experience Proof

**Purpose**: Validate prior work experience and reliability.

**Accepted Formats:**
- PDF
- PNG / JPG

**Required Details:**
- Job Title / Role
- Company Name
- Duration of Employment

**Example Contents:**
```
Experience Letter
John Doe worked as Electrician at XYZ Ltd for 5 years
```

**Features Extracted:**
- `experience_years` → Total years of relevant experience
- `experience_reference_count` → Number of reference letters or proof documents

---

## 5️⃣ Portfolio Work

**Purpose**: Demonstrate practical skills and quality of work.

**Accepted Formats:**
- PNG / JPG
- Short video clips (optional)

**Required Details:**
- Images of completed projects relevant to their service
- Clear and high-quality visuals showing work done

**Example Contents:**
```
Portfolio Image
Service: Electrician
Completed Work Example: Wiring setup in residential house
```

**Features Extracted:**
- `portfolio_count` → Number of portfolio images uploaded
- `portfolio_quality_score` → Score (0–1) based on image clarity, completeness

---

## 6️⃣ Summary Table of Required Documents

| Document | Format | Key Contents | Feature Extracted |
| --- | --- | --- | --- |
| Identity Document | PDF, PNG, JPG | Name, DOB, ID number | `identity_verified` |
| Certifications | PDF, PNG, JPG | Certificate level, service, issuer, date | `certification_count`, `highest_cert_level`, `cert_issuer_reputation` |
| Business Registration | PDF, PNG, JPG | Company name, owner, registration number | `business_registered` |
| Experience Proof | PDF, PNG, JPG | Job title, company, duration | `experience_years`, `experience_reference_count` |
| Portfolio Work | PNG, JPG, Video | Completed work images or videos | `portfolio_count`, `portfolio_quality_score` |

---

## Notes & Best Practices

### Legibility
All documents must be clear and readable. OCR will fail on blurry or low-resolution scans.

### Consistency
Dates, names, and service types should match across documents.

### Portfolio
More images/videos provide better evidence of skills and improve credibility score.

### File Naming
For testing, files can be named like:
- `identity_1.pdf`
- `certification_1.pdf`
- `business_1.pdf`
- `experience_1_1.pdf `
- `experience_1_2.pdf `
- `portfolio_1.png`

This naming convention helps organize documents by provider ID and type.

### Upload Process
1. Provider uploads documents in supported formats
2. System extracts features via OCR (pytesseract)
3. Features are encoded for ML model
4. Credibility score is predicted
5. Score is mapped to credibility level

### Quality Assurance
- Verify all required documents are present
- Check document clarity before processing
- Validate extracted features for consistency
- Review credibility predictions with domain experts
- Flag suspicious or incomplete submissions for manual review

---

## Data Flow

```
Provider Documents
    ↓
OCR Text Extraction (pytesseract)
    ↓
Feature Parsing & Validation
    ↓
Label Encoding (Categorical → Numerical)
    ↓
ML Model Input Vector
    ↓
Credibility Score Prediction (0-100)
    ↓
Level Assignment (Beginner / Intermediate / Professional)
```

---

## Troubleshooting

### OCR Not Working
- Ensure document image is clear and high resolution (200+ DPI recommended)
- Check poppler installation and path configuration (Windows)
- Verify pytesseract is properly installed

### Feature Extraction Issues
- Ensure keywords match document templates (e.g., "identity card", "certification", "experience")
- Check for typos or variations in document text
- Consider fuzzy matching for keyword detection

### Inconsistent Predictions
- Review extracted features for correctness
- Verify label encoders match training data categories
- Check if new service categories are present in documents
- Validate model predictions on known test cases