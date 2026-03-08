import pandas as pd
import os

# Define the data structure
data = {
    'IP': ['192.168.1.1', '192.168.1.2'],
    'Username': ['admin', 'admin'],
    'Password': ['password', 'password']
}

# Create a DataFrame
df = pd.DataFrame(data)

# Define the file path
file_path = 'c:/Users/promi.deb/Desktop/CDN automation/routers.xlsx'

# Ensure directory exists
os.makedirs(os.path.dirname(file_path), exist_ok=True)

# Write to Excel
try:
    df.to_excel(file_path, index=False)
    print(f"Successfully created template at: {file_path}")
except Exception as e:
    print(f"Error creating excel file: {e}")
