# NIH Reporter API Client

This script fetches award data from the NIH Reporter API for fiscal years 2009-2024 and processes it according to the specified format.

## Setup

Install the required dependencies:
```bash
pip install -r requirements.txt
```

## Usage

Run the script:
```bash
python nih_api_client.py
```

The script will:
1. Fetch award data for fiscal years 2009-2024
2. Process the data according to the specified format
3. Save the results to a CSV file named `nih_awards_YYYYMMDD.csv`

## Output Fields

The script processes the following fields from the NIH Reporter API:
- Organization ID (IPF)
- Project Number
- Funding Mechanism
- NIH Reference
- PI Name
- PI Person ID
- Project Title
- Department Name
- NIH Department Combining Name
- NIH MC Combining Name
- Direct Cost
- Indirect Cost
- Funding
- Congressional District
- City
- State/Country Name
- ZIP Code
- Attributed to Medical School
- Medical School Location
- Institution Type
- Award Notice Date
- Opportunity Number
- Major Component Name
- Medical School Flag
- Medical School Name
- Multi-Campus Institution
- Fiscal Year
- Activity Code
- Application Type Code

## Notes

- Some fields (medical_school_location, medical_school_name, multi_campus_institution) are not available in the API and will be set to None
- The script uses pagination to handle large result sets
- The API has rate limits, so the script includes error handling for API responses 