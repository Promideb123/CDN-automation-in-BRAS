import re
import pandas as pd

log_file = 'queue_automation.log'
output_file = 'error_report_parsed.csv'

error_list = []
current_ip = None

# Regex patterns
ip_pattern = re.compile(r'Processing Router: (\d+\.\d+\.\d+\.\d+)')
error_pattern = re.compile(r'ERROR - (.*)') # Generic error capture

try:
    with open(log_file, 'r') as f:
        for line in f:
            ip_match = ip_pattern.search(line)
            if ip_match:
                current_ip = ip_match.group(1)
            
            if 'ERROR' in line:
                # Capture the error message
                msg = line.split('ERROR - ')[1].strip()
                if current_ip:
                    error_list.append({'IP': current_ip, 'Error': msg})

    if error_list:
        df = pd.DataFrame(error_list)
        df.to_csv(output_file, index=False)
        print(f"Extracted {len(df)} errors to {output_file}")
        print(df.head())
    else:
        print("No errors found in log.")

except Exception as e:
    print(f"Failed to parsing log: {e}")
