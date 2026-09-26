import os
import email
import email.policy
import csv
import json
import uuid

EML_DIR = r"C:\MyProjects\RAG\data\documents\queue-emails"
CSV_PATH = r"C:\MyProjects\RAG\data\documents\ai_meta_info_uw_assistant.csv"
OUTPUT_JSON = r"C:\MyProjects\RAG\web\tirsweb\data.json"

# 1. Load CSV data to map subjects to Cytora JSON
csv_data = {}
if os.path.exists(CSV_PATH):
    with open(CSV_PATH, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            subject = row.get('subject', '').strip()
            # Normalize subject for matching (remove special chars/spaces)
            norm_sub = ''.join(e for e in subject if e.isalnum()).lower()
            csv_data[norm_sub] = row

submissions = []

# 2. Process EML files
if os.path.exists(EML_DIR):
    for filename in os.listdir(EML_DIR):
        if not filename.endswith('.eml'):
            continue
            
        filepath = os.path.join(EML_DIR, filename)
        with open(filepath, 'rb') as f:
            msg = email.message_from_binary_file(f, policy=email.policy.default)
        
        eml_subject = msg.get('subject', 'No Subject')
        eml_from = msg.get('from', 'Unknown Sender')
        eml_to = msg.get('to', '')
        eml_cc = msg.get('cc', '')
        eml_date = msg.get('date', '2026-09-26T12:00:00Z')
        
        # Try to match with CSV
        norm_eml_sub = ''.join(e for e in eml_subject if e.isalnum()).lower()
        
        # Simple fuzzy match or exact match on normalized
        matched_row = csv_data.get(norm_eml_sub)
        
        if not matched_row:
            # Try matching filename to CSV subject
            norm_file = ''.join(e for e in filename.replace('.eml', '') if e.isalnum()).lower()
            # Find closest match
            for k, v in csv_data.items():
                if norm_file in k or k in norm_file:
                    matched_row = v
                    break

        if matched_row:
            syselmid = matched_row.get('syselmid')
            json_str = matched_row.get('trc_json_response', '{}').strip()
            if json_str.startswith('"') and json_str.endswith('"'):
                json_str = json_str[1:-1].replace('""', '"')
        else:
            syselmid = f"SUB-{uuid.uuid4().hex[:8]}"
            json_str = '{}'
            
        if not syselmid:
             syselmid = f"SUB-{uuid.uuid4().hex[:8]}"

        try:
            trc_data = json.loads(json_str)
        except:
            trc_data = {"Entries": []}
            
        entries = trc_data.get("Entries", [])
        insured_name = "Unknown Insured"
        lob = "Unknown LOB"
        for entry in entries:
            if entry.get("FieldName") == "Insured Name":
                val = entry.get("ExtractedValue")
                if val: insured_name = val
            elif entry.get("FieldName") == "Sub Department":
                val = entry.get("ExtractedValue")
                if val: lob = val
                
        # Extract body text (prefer HTML)
        body_text = ""
        html_body = ""
        plain_body = ""
        
        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                if ctype == "text/html":
                    html_body += part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8', errors='ignore')
                elif ctype == "text/plain":
                    plain_body += part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8', errors='ignore')
        else:
            ctype = msg.get_content_type()
            if ctype == "text/html":
                html_body = msg.get_payload(decode=True).decode(msg.get_content_charset() or 'utf-8', errors='ignore')
            else:
                plain_body = msg.get_payload(decode=True).decode(msg.get_content_charset() or 'utf-8', errors='ignore')
                
        body_text = html_body if html_body else plain_body
                
        sub = {
            "id": syselmid,
            "status": "UNASSIGNED",
            "clearance_status": "TA_REVIEW" if len(submissions) % 3 == 0 else "CLEARED",
            "confidence_index": 0.98 - (len(submissions) * 0.01),
            "email": {
                "subject": eml_subject,
                "from": str(eml_from),
                "to": str(eml_to),
                "cc": str(eml_cc),
                "date": str(eml_date),
                "filename": filename,
                "body": body_text
            },
            "cytora_entries": entries,
            "stitch_worksheet": {
                "account_overview": {
                    "insured_name": insured_name
                },
                "deal_metrics": {
                    "line_of_business": lob
                }
            }
        }
        submissions.append(sub)

data_out = {"submissions": submissions}

with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
    json.dump(data_out, f, indent=2)

print(f"Processed {len(submissions)} EML files into data.json")
