import csv
import os
import re
import json

def clean_name(name):
    if not name:
        return ""
    # Remove extra whitespace and capitalize
    name = re.sub(r'\s+', ' ', name).strip()
    return name.title()

def get_first_name(first, full):
    if first.strip():
        return clean_name(first)
    # Parse from full name
    full_cleaned = clean_name(full)
    if full_cleaned:
        return full_cleaned.split(' ')[0]
    return ""

def get_last_name(last, full):
    if last.strip():
        return clean_name(last)
    # Parse from full name
    full_cleaned = clean_name(full)
    if full_cleaned:
        parts = full_cleaned.split(' ')
        if len(parts) > 1:
            return parts[-1]
    return ""

def process():
    output_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(output_dir, 'config.json')
    
    csv_path = "stakeholder_directory.csv" # default fallback
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as cf:
                config_data = json.load(cf)
                csv_path = config_data.get('master_csv_path', csv_path)
        except Exception as e:
            print(f"Warning: Could not parse config.json: {e}")
            
    if not os.path.exists(csv_path):
        # Check if the file name exists in downloads folder
        alt_path = os.path.expanduser(r"~\Downloads\MyCity - Stakeholder Directory, Meetings, Deliverables (1) - Current Stakeholder Directory .csv")
        if os.path.exists(alt_path):
            csv_path = alt_path
        else:
            print(f"Error: Master CSV not found at {csv_path}")
            return

    with open(csv_path, mode='r', encoding='utf-8') as f:
        lines = f.readlines()

    header_idx = -1
    for i, line in enumerate(lines):
        if "MyCity Organization" in line:
            header_idx = i
            break

    if header_idx == -1:
        print("Error: Could not find header row in CSV.")
        return

    reader = csv.reader(lines[header_idx:])
    header = next(reader)
    rows = list(reader)

    # Required columns
    col_map = {col: header.index(col) for col in [
        'MyCity Organization', 'Org Type', 'Full Name', 'First Name', 'Last Name',
        'Title', 'Status', 'Employer', 'Phone', 'Project Email (calculated)',
        'Native Work Email', 'OTI Email'
    ] if col in header}

    city_employees = []
    vendors = []

    for r in rows:
        if len(r) < max(col_map.values()) + 1:
            continue
        
        org_type = r[col_map['Org Type']].strip()
        org = r[col_map['MyCity Organization']].strip()
        full_name = r[col_map['Full Name']].strip()
        status = r[col_map['Status']].strip()
        
        if not full_name:
            continue

        first_name_raw = r[col_map['First Name']].strip()
        last_name_raw = r[col_map['Last Name']].strip()
        title = r[col_map['Title']].strip()
        employer = r[col_map['Employer']].strip()
        phone = r[col_map['Phone']].strip()
        proj_email = r[col_map['Project Email (calculated)']].strip()
        native_email = r[col_map['Native Work Email']].strip()
        oti_email = r[col_map['OTI Email']].strip()

        # Clean names
        first_name = get_first_name(first_name_raw, full_name)
        last_name = get_last_name(last_name_raw, full_name)
        clean_full_name = f"{first_name} {last_name}".strip()

        # Email selection logic
        best_email = ""
        email_source = ""
        
        if org_type.lower() == 'city':
            # For City employees, prefer project email, then native, then OTI
            for email, label in [(proj_email, 'Project Email'), (native_email, 'Native Email'), (oti_email, 'OTI Email')]:
                if email and '@' in email:
                    best_email = email
                    email_source = label
                    break
        else:
            # For Vendors, prefer native (company) email, then project email, then OTI
            for email, label in [(native_email, 'Native Email'), (proj_email, 'Project Email'), (oti_email, 'OTI Email')]:
                if email and '@' in email:
                    best_email = email
                    email_source = label
                    break

        # Skip if no email found
        if not best_email:
            continue

        contact_info = {
            'Organization': org,
            'Org Type': org_type,
            'Full Name': clean_full_name,
            'First Name': first_name,
            'Last Name': last_name,
            'Title': title,
            'Status': status,
            'Employer': employer if employer else org,
            'Phone': phone,
            'Email': best_email,
            'Email Source': email_source
        }

        if org_type.lower() == 'city' and org.upper() != 'OTI':
            city_employees.append(contact_info)
        elif org_type.lower() == 'vendor' and org.upper() != 'MICROSOFT':
            vendors.append(contact_info)

    # Write City Employees CSV
    city_fields = ['Organization', 'Org Type', 'Full Name', 'First Name', 'Last Name', 'Title', 'Status', 'Employer', 'Phone', 'Email', 'Email Source']
    city_out_path = os.path.join(output_dir, 'city_employees_outreach.csv')
    with open(city_out_path, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=city_fields)
        writer.writeheader()
        writer.writerows(city_employees)

    # Write Vendors CSV
    vendor_out_path = os.path.join(output_dir, 'vendor_employees_outreach.csv')
    with open(vendor_out_path, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=city_fields)
        writer.writeheader()
        writer.writerows(vendors)

    print(f"Successfully processed contacts:")
    print(f"  City Employees (non-OTI): {len(city_employees)} -> Saved to {city_out_path}")
    print(f"  Vendors (non-Microsoft): {len(vendors)} -> Saved to {vendor_out_path}")

if __name__ == "__main__":
    process()
