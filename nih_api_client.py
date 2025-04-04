import os
import requests
import pandas as pd
from datetime import datetime, date
import time
import json
import calendar

class NIHReporterClient:
    def __init__(self):
        self.base_url = "https://api.reporter.nih.gov/v2"
        self.headers = {
            "Content-Type": "application/json"
        }
        self.max_limit = 500
        self.max_offset = 14999
        
        # BRIMR standardization rules
        self.organization_standardization = {
            "COLLEGE OF MEDICINE": "",
            "MEDICAL CENTER": "",
            "HEALTH CENTER": "",
            "HEALTH SCIENCE CENTER": "",
            "SCHOOL OF MEDICINE": "",
            "SCHOOL OF MEDICINE & DENTISTRY": "SCHOOLS OF MEDICINE",
            "OVERALL MEDICAL": "SCHOOLS OF MEDICINE"
        }
        
        self.city_standardization = {
            "NEW YORK CITY": "NEW YORK",
            "SAN FRANCISCO": "SAN FRANCISCO",
            "LOS ANGELES": "LOS ANGELES"
        }
        
        self.special_cases = {
            "MAYO CLINIC ROCHESTER": "MAYO CLINIC SCHOOL OF MEDICINE",
            "CASE WESTERN RESERVE UNIVERSITY": "CASE WESTERN RESERVE UNIVERSITY SCHOOL OF MEDICINE",
            "CLEVELAND CLINIC LERNER": "CASE WESTERN RESERVE UNIVERSITY SCHOOL OF MEDICINE",
            "HENRY FORD HEALTH SYSTEM": "HENRY FORD HEALTH SYSTEM/MICHIGAN STATE UNIVERSITY",
            "MICHIGAN STATE UNIVERSITY": "HENRY FORD HEALTH SYSTEM/MICHIGAN STATE UNIVERSITY"
        }

    def standardize_organization_name(self, name):
        """Standardize organization name according to BRIMR rules"""
        # Handle special cases first
        for key, value in self.special_cases.items():
            if key in name.upper():
                return value
        
        # Remove common suffixes
        standardized = name.upper()
        for suffix, replacement in self.organization_standardization.items():
            standardized = standardized.replace(suffix, replacement)
        
        # Clean up any double spaces
        standardized = ' '.join(standardized.split())
        
        return standardized

    def standardize_city_name(self, city):
        """Standardize city name according to BRIMR rules"""
        standardized = city.upper()
        for key, value in self.city_standardization.items():
            if key in standardized:
                return value
        return standardized

    def get_last_day_of_month(self, year, month):
        """Get the last day of the given month"""
        return calendar.monthrange(year, month)[1]

    def get_awards(self, fiscal_years=None, limit=500):
        """
        Fetch awards data from NIH Reporter API
        """
        if fiscal_years is None:
            fiscal_years = [2024]  # Only 2024

        all_awards = []
        
        for fiscal_year in fiscal_years:
            print(f"\nProcessing fiscal year {fiscal_year}...")
            
            # Process each month
            for month in range(1, 13):
                print(f"\nProcessing month {month}...")
                
                # Get the last day of the month
                last_day = self.get_last_day_of_month(fiscal_year, month)
                
                # First, get the total count for this month
                count_payload = {
                    "criteria": {
                        "fiscal_years": [fiscal_year],
                        "organization_type": ["SCHOOLS OF MEDICINE"],  # Only medical schools
                        "award_notice_date": {
                            "from_date": f"{fiscal_year}-{month:02d}-01",
                            "to_date": f"{fiscal_year}-{month:02d}-{last_day}"
                        }
                    },
                    "limit": 1,
                    "offset": 0
                }
                
                try:
                    print("Getting total count...")
                    count_response = requests.post(
                        f"{self.base_url}/projects/search",
                        headers=self.headers,
                        json=count_payload
                    )
                    
                    if count_response.status_code == 200:
                        count_data = count_response.json()
                        total_count = count_data.get('meta', {}).get('total', 0)
                        print(f"Total awards for month {month}: {total_count}")
                    else:
                        print(f"Error getting total count: {count_response.text}")
                        continue
                except Exception as e:
                    print(f"Error getting total count: {str(e)}")
                    continue
                
                if total_count == 0:
                    print(f"No awards found for month {month}, skipping...")
                    continue
                
                # Calculate number of chunks needed
                num_chunks = (total_count + self.max_limit - 1) // self.max_limit
                print(f"Will fetch data in {num_chunks} chunks of {self.max_limit} records each")
                
                # Fetch data in chunks
                for chunk in range(num_chunks):
                    start_offset = chunk * self.max_limit
                    
                    # Check if we've hit the maximum offset limit
                    if start_offset > self.max_offset:
                        print(f"\nWarning: Hit maximum offset limit of {self.max_offset}")
                        print("To get more data, we need to further narrow down the search criteria")
                        break
                    
                    print(f"\nFetching chunk {chunk + 1} of {num_chunks} (offset {start_offset})...")
                    
                    payload = {
                        "criteria": {
                            "fiscal_years": [fiscal_year],
                            "organization_type": ["SCHOOLS OF MEDICINE"],  # Only medical schools
                            "award_notice_date": {
                                "from_date": f"{fiscal_year}-{month:02d}-01",
                                "to_date": f"{fiscal_year}-{month:02d}-{last_day}"
                            }
                        },
                        "limit": self.max_limit,
                        "offset": start_offset,
                        "sort_field": "project_start_date",
                        "sort_order": "desc"
                    }

                    try:
                        response = requests.post(
                            f"{self.base_url}/projects/search",
                            headers=self.headers,
                            json=payload
                        )
                        
                        if response.status_code != 200:
                            print(f"Error fetching data: {response.text}")
                            continue

                        data = response.json()
                        results = data.get('results', [])
                        
                        if not results:
                            print("No more results found.")
                            break

                        all_awards.extend(results)
                        print(f"Retrieved {len(results)} awards (Total: {len(all_awards)})")
                        
                        # Add a small delay to avoid rate limiting
                        time.sleep(0.5)
                        
                    except Exception as e:
                        print(f"Error occurred: {str(e)}")
                        continue

                print(f"\nTotal awards retrieved for month {month}: {len(all_awards)}")
                if len(all_awards) < total_count:
                    print(f"Warning: Only retrieved {len(all_awards)} out of {total_count} total awards")
                    print("This might be due to API limitations or rate limiting")

        return all_awards

    def format_currency(self, amount):
        """Format currency values like BRIMR"""
        if amount is None or amount == 0:
            return "$0"
        return f"${amount:,.0f}"

    def process_awards(self, awards):
        """
        Process awards data into the required format matching MedicalSchoolsOnly_2024_B.xlsx
        """
        processed_data = []
        
        for award in awards:
            # Get organization data
            org = award.get('organization', {})
            
            # Get award data - this is where we need to fix the financial data mapping
            award_data = award.get('award_data', {})
            
            # Format dates like BRIMR (MM/DD/YY)
            award_date = award.get('award_notice_date')
            if award_date:
                try:
                    date_obj = datetime.strptime(award_date, '%Y-%m-%d')
                    award_date = date_obj.strftime('%m/%d/%y')
                except:
                    pass
            
            # Get PI data
            pi_data = award.get('contact_pi', {})
            
            # Get project data
            project_data = award.get('project', {})
            
            # Standardize organization and city names
            org_name = self.standardize_organization_name(org.get('org_name', ''))
            city = self.standardize_city_name(org.get('city_name', ''))
            
            # Get financial data - fixed mapping based on API documentation
            # The funding data is in the award_data object
            direct_cost = award_data.get('direct_cost_amt', 0) or 0
            indirect_cost = award_data.get('indirect_cost_amt', 0) or 0
            total_cost = award_data.get('total_cost', 0) or (direct_cost + indirect_cost) or 0
            
            # Print raw financial data for debugging
            if len(processed_data) <= 5:  # Print first 5 records for verification
                print(f"\nRaw financial data for {org_name}:")
                print(f"Award Data: {json.dumps(award_data, indent=2)}")
            
            processed_award = {
                'ORGANIZATION NAME': org_name,
                'ORGANIZATION ID (IPF)': org.get('org_duns', ''),  # Using DUNS number as IPF
                'PROJECT NUMBER': award.get('project_num', ''),
                'FUNDING MECHANISM': award.get('funding_mechanism', ''),
                'NIH REFERENCE': award.get('project_num', ''),
                'PI NAME': pi_data.get('full_name', ''),
                'PI PERSON ID': pi_data.get('profile_id', ''),
                'PROJECT TITLE': project_data.get('project_title', ''),
                'DEPT NAME': org.get('dept_name', ''),
                'NIH DEPT COMBINING NAME': org.get('dept_name', ''),
                'NIH MC COMBINING NAME': org_name,
                'DIRECT COST': self.format_currency(direct_cost),
                'INDIRECT COST': self.format_currency(indirect_cost),
                'FUNDING': self.format_currency(total_cost),
                'CONGRESSIONAL DISTRICT': org.get('congressional_district', ''),
                'CITY': city,
                'STATE OR COUNTRY NAME': org.get('state_name', ''),
                'ZIP CODE': org.get('zip_code', ''),
                'ATTRIBUTED TO MEDICAL SCHOOL': 'Y',  # Always Y since we're only getting medical schools
                'MEDICAL SCHOOL LOCATION': org_name,  # Always the org name since we're only getting medical schools
                'INSTITUTION TYPE': 'SCHOOLS OF MEDICINE',  # Always this for medical schools
                'AWARD NOTICE DATE': award_date,
                'OPPORTUNITY NUMBER': award.get('opportunity_number', ''),
                'MAJOR COMPONENT NAME': org_name,
                'MEDICAL SCHOOL FLAG': 'Y',  # Always Y since we're only getting medical schools
                'MEDICAL SCHOOL NAME': org_name,  # Always the org name since we're only getting medical schools
                'MULTI CAMPUS INSTITUTION': 'N',  # Not available in API
                'ACTIVITY CODE': award.get('activity_code', ''),
                'APPLICATION TYPE CODE': award.get('application_type', '')
            }
            processed_data.append(processed_award)
            
            # Print sample financial data for debugging
            if len(processed_data) <= 5:  # Print first 5 records for verification
                print(f"\nProcessed financial data for {org_name}:")
                print(f"Direct Cost: {direct_cost}")
                print(f"Indirect Cost: {indirect_cost}")
                print(f"Total Cost: {total_cost}")
        
        return processed_data

def main():
    # Initialize the client
    client = NIHReporterClient()
    
    # Fetch awards data
    print("Starting to fetch medical school awards data for 2024...")
    awards = client.get_awards()
    
    if not awards:
        print("No awards were retrieved. Please check the error messages above.")
        return
    
    # Process the data
    print(f"\nProcessing {len(awards)} awards...")
    processed_data = client.process_awards(awards)
    
    # Convert to DataFrame and save to CSV
    df = pd.DataFrame(processed_data)
    
    # Reorder columns to match MedicalSchoolsOnly_2024_B.xlsx
    column_order = [
        'ORGANIZATION NAME', 'ORGANIZATION ID (IPF)', 'PROJECT NUMBER', 'FUNDING MECHANISM',
        'NIH REFERENCE', 'PI NAME', 'PI PERSON ID', 'PROJECT TITLE', 'DEPT NAME',
        'NIH DEPT COMBINING NAME', 'NIH MC COMBINING NAME', 'DIRECT COST', 'INDIRECT COST',
        'FUNDING', 'CONGRESSIONAL DISTRICT', 'CITY', 'STATE OR COUNTRY NAME', 'ZIP CODE',
        'ATTRIBUTED TO MEDICAL SCHOOL', 'MEDICAL SCHOOL LOCATION', 'INSTITUTION TYPE',
        'AWARD NOTICE DATE', 'OPPORTUNITY NUMBER', 'MAJOR COMPONENT NAME', 'MEDICAL SCHOOL FLAG',
        'MEDICAL SCHOOL NAME', 'MULTI CAMPUS INSTITUTION', 'ACTIVITY CODE', 'APPLICATION TYPE CODE'
    ]
    df = df[column_order]
    
    # Print detailed statistics
    print("\nData Statistics:")
    print(f"Total records: {len(df)}")
    print("\nNon-null counts per column:")
    print(df.count())
    print("\nSample of processed data:")
    print(df.head())
    
    # Save to CSV
    output_file = f"MedicalSchoolsOnly_2024_{datetime.now().strftime('%Y%m%d')}.csv"
    df.to_csv(output_file, index=False)
    print(f"\nData saved to {output_file}")
    print(f"Total records processed: {len(processed_data)}")

if __name__ == "__main__":
    main()