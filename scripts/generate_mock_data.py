import csv
import json
import uuid
import os

csv_path = r"C:\MyProjects\RAG\data\documents\ai_meta_info_uw_assistant.csv"
output_path = r"C:\MyProjects\RAG\web\tirsweb\data.json"

submissions = []

if os.path.exists(csv_path):
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            syselmid = row.get('syselmid', f"SUB-{uuid.uuid4().hex[:8]}")
            if not syselmid:
                syselmid = f"SUB-{uuid.uuid4().hex[:8]}"
            subject = row.get('subject', 'No Subject')
            
            # parse json
            json_str = row.get('trc_json_response', '{}').strip()
            # Handle empty or malformed json strings
            if json_str.startswith('"') and json_str.endswith('"'):
                json_str = json_str[1:-1].replace('""', '"')
            
            try:
                trc_data = json.loads(json_str)
            except Exception as e:
                trc_data = {"Entries": []}
                
            entries = trc_data.get("Entries", [])
            
            insured_name = "Unknown"
            lob = "Unknown"
            for entry in entries:
                if entry.get("FieldName") == "Insured Name":
                    val = entry.get("ExtractedValue")
                    if val: insured_name = val
                elif entry.get("FieldName") == "Sub Department":
                    val = entry.get("ExtractedValue")
                    if val: lob = val
            
            sub = {
                "id": syselmid,
                "status": "UNASSIGNED",
                "clearance_status": "CLEARED" if i % 2 == 0 else "TA_REVIEW",
                "confidence_index": 0.95 - (i * 0.02),
                "email": {
                    "subject": subject,
                    "from": "broker@example.com",
                    "date": f"2026-09-25T14:{30+i:02d}:00Z"
                },
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

with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(data_out, f, indent=2)

print(f"Successfully processed {len(submissions)} submissions into data.json")
