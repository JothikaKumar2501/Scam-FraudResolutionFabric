# ANZ Bank Fraud Detection System - Dataset Documentation

## Overview
This directory contains the standardized datasets for the ANZ Bank fraud detection system. All datasets have been updated to version 2.0 with improved structure, consistency, and data quality.

## Dataset Files

### 1. customer_demographic.json
**Description**: Customer demographic and profile information for fraud risk assessment.

**Structure**:
```json
{
  "metadata": {
    "version": "2.0",
    "created_date": "2024-01-15",
    "last_updated": "2024-01-15",
    "description": "ANZ Bank customer demographic data for fraud detection system",
    "total_customers": 10,
    "data_quality_score": 0.95
  },
  "customers": [
    {
      "customer_id": "AU-CUST7712",
      "personal_information": {
        "name": "Oliver James Thompson",
        "date_of_birth": "1989-05-17",
        "gender": "Male",
        "id_verified": true,
        "digital_literacy_level": "High"
      },
      "contact_information": {
        "address": "27 Eucalyptus Drive, Blackburn VIC 3130",
        "email": "oliver.thompson@gmail.com",
        "phone": "0468 329 174",
        "preferred_contact": "Email"
      },
      "background": {
        "citizenship": "Australian",
        "marital_status": "Married",
        "dependents": 2,
        "language_preference": "English"
      },
      "employment": {
        "status": "Full-time",
        "occupation": "Software Engineer",
        "employer": "TechSolutions Pty Ltd",
        "annual_income": 110000
      },
      "customer_details": {
        "segment": "Premium",
        "customer_since": "2015-07-23",
        "home_branch": "Melbourne CBD",
        "known_device_familiarity_score": 0.95,
        "prior_alerts": 1,
        "scam_education_completed": true,
        "risk_profile": "Low",
        "fraud_flag": false,
        "notes": "Tech-savvy customer with good security awareness"
      }
    }
  ]
}
```

**Key Fields**:
- `customer_id`: Unique identifier (format: AU-CUST####)
- `digital_literacy_level`: "High", "Medium", "Low"
- `risk_profile`: "Low", "Medium", "High", "Very High"
- `segment`: "Premium", "Standard", "Vulnerable"
- `fraud_flag`: Boolean indicating if customer has fraud history

### 2. Customer_Transaction_History.json
**Description**: Transaction history with fraud detection flags and metadata.

**Structure**:
```json
{
  "metadata": {
    "version": "2.0",
    "created_date": "2024-01-15",
    "last_updated": "2024-01-15",
    "description": "ANZ Bank customer transaction history for fraud detection system",
    "total_transactions": 20,
    "date_range": {
      "start": "2024-01-01",
      "end": "2024-01-15"
    },
    "data_quality_score": 0.95
  },
  "transactions": [
    {
      "transaction_id": "TXN-2024-001",
      "customer_id": "AU-CUST7712",
      "amount": 150.00,
      "currency": "AUD",
      "transaction_type": "Payment",
      "transaction_date": "2024-01-15",
      "transaction_time": "09:15:30",
      "bank_id": "ANZ001",
      "branch_id": "BR001",
      "account_number": "1234567890",
      "payee_payer_name": "Woolworths",
      "description": "Grocery shopping",
      "ip_address": "203.45.67.89",
      "ip_address_country": "Australia",
      "device_id": "DEV-001",
      "device_model": "iPhone 14",
      "status": "Completed",
      "is_flagged": false,
      "flag_reason": null,
      "category": "Groceries",
      "known_device": true,
      "merchant_category_code": "5411"
    }
  ]
}
```

**Key Fields**:
- `transaction_id`: Unique identifier (format: TXN-YYYY-###)
- `amount`: Numeric value in AUD
- `is_flagged`: Boolean indicating fraud detection
- `flag_reason`: Description of why transaction was flagged
- `known_device`: Boolean indicating if device is recognized
- `merchant_category_code`: Standard MCC for transaction categorization

### 3. Enhanced_Customer_Call_History.json
**Description**: Call center interactions and fraud investigation records.

**Structure**:
```json
{
  "metadata": {
    "version": "2.0",
    "created_date": "2024-01-15",
    "last_updated": "2024-01-15",
    "description": "ANZ Bank customer call history for fraud detection system",
    "total_calls": 15,
    "date_range": {
      "start": "2024-01-01",
      "end": "2024-01-15"
    },
    "data_quality_score": 0.95
  },
  "calls": [
    {
      "call_id": "CALL-2024-001",
      "date": "2024-01-15",
      "time": "06:42:00",
      "alert_id": "ALRT-AU-CUST7712-1",
      "customer_id": "AU-CUST7712",
      "analyst_name": "Olivia S. (Fraud Ops Trainee)",
      "analyst_team": "Fraud Ops East",
      "call_type": "Inbound",
      "call_outcome_category": "No Response",
      "follow_up_required": true,
      "next_action": "Follow up",
      "memo": "High-risk international transfer flagged post password reset.",
      "channel": "Internet Banking",
      "call_duration": "00:04:09",
      "language": "English",
      "location": "NSW, Australia",
      "risk_level": "High",
      "escalated": false,
      "customer_profile": "Low-risk",
      "prior_alerts": 1,
      "has_seen_education_material": true
    }
  ]
}
```

**Key Fields**:
- `call_id`: Unique identifier (format: CALL-YYYY-###)
- `alert_id`: Links to FTP alert
- `call_outcome_category`: "No Response", "Customer reached", "Voicemail left", "Disconnected"
- `risk_level`: "Low", "Medium", "High", "Very High", "Critical"
- `escalated`: Boolean indicating if case was escalated
- `customer_profile`: Customer risk classification

### 4. FTP.json
**Description**: Fraud Transaction Protocol alerts with risk scoring and escalation levels.

**Structure**:
```json
{
  "metadata": {
    "version": "2.0",
    "created_date": "2024-01-15",
    "last_updated": "2024-01-15",
    "description": "ANZ Bank Fraud Transaction Protocol (FTP) alerts for fraud detection system",
    "total_alerts": 12,
    "date_range": {
      "start": "2024-01-01",
      "end": "2024-01-15"
    },
    "data_quality_score": 0.95
  },
  "alerts": [
    {
      "alert_id": "ALRT-AU-CUST7712-1",
      "customer_id": "AU-CUST7712",
      "rule_id": "RUL-TX901",
      "strategy": "Large Fund Transfer Post Password Change",
      "queue": "High-Risk Behaviour Queue",
      "priority": "High",
      "status": "Open",
      "description": "Password updated at 09:12; $15,000 transferred at 09:38 to unknown PayID recipient",
      "alert_date": "2024-01-12",
      "alert_time": "09:40:10",
      "transaction_id": "TXN-2024-011",
      "amount": 15000.00,
      "currency": "AUD",
      "risk_score": 85,
      "escalation_level": "Tier 1"
    }
  ]
}
```

**Key Fields**:
- `alert_id`: Unique identifier (format: ALRT-AU-CUST####-###)
- `rule_id`: Fraud detection rule identifier
- `strategy`: Fraud detection strategy name
- `queue`: Processing queue assignment
- `priority`: "Low", "Medium", "High", "Critical"
- `risk_score`: Numeric risk score (0-100)
- `escalation_level`: "Tier 1", "Tier 2", "Tier 3"

## Data Relationships

### Customer Relationships
- `customer_id` links customers across all datasets
- Each customer can have multiple transactions, calls, and alerts
- Customer demographic data provides context for risk assessment

### Transaction Relationships
- `transaction_id` links transactions to FTP alerts
- `customer_id` links transactions to customer profiles
- Transaction flags trigger FTP alerts

### Alert Relationships
- `alert_id` links FTP alerts to call history
- `transaction_id` links alerts to specific transactions
- `customer_id` links alerts to customer profiles

### Call Relationships
- `alert_id` links calls to FTP alerts
- `customer_id` links calls to customer profiles
- Call outcomes influence alert resolution

## Data Quality Improvements

### Version 2.0 Enhancements
1. **Consistent Naming**: All fields use snake_case convention
2. **Data Types**: Proper numeric and boolean types
3. **Metadata**: Version tracking and quality scoring
4. **Relationships**: Proper foreign key relationships
5. **Validation**: Realistic dates and data values
6. **Completeness**: All required fields populated

### Validation Rules
- Customer IDs must follow AU-CUST#### format
- Transaction IDs must follow TXN-YYYY-### format
- Alert IDs must follow ALRT-AU-CUST####-### format
- Call IDs must follow CALL-YYYY-### format
- All dates must be realistic (past dates only)
- Amounts must be positive numbers
- Risk scores must be 0-100 range

## Usage Guidelines

### For Development
1. Use customer_id as the primary key for customer lookups
2. Use transaction_id to link transactions to alerts
3. Use alert_id to link alerts to call history
4. Check metadata for data quality scores
5. Validate data relationships before processing

### For Testing
1. Use realistic customer scenarios
2. Test with various fraud patterns
3. Validate alert escalation logic
4. Test call outcome workflows
5. Verify data integrity across datasets

### For Production
1. Monitor data quality scores
2. Validate relationships regularly
3. Update metadata timestamps
4. Maintain audit trails
5. Follow ANZ Bank compliance requirements

## Compliance Notes
- All data follows ANZ Bank privacy policies
- Customer information is anonymized for testing
- Transaction amounts are realistic but fictional
- Dates are recent but not current
- IP addresses are fictional for security

## Support
For questions about the dataset structure or usage, refer to:
- ANZ Bank Fraud Detection System Documentation
- Data Schema Specifications
- Compliance Guidelines
- Testing Procedures
