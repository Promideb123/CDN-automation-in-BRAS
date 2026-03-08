
import pandas as pd
import paramiko
import time
import socket
import logging
import re

# Configure logging
logging.basicConfig(
    filename='queue_automation.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
logging.getLogger('').addHandler(console)

def connect_to_router(ip, username, password):
    """Establishes an SSH connection to the MikroTik router."""
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ip, username=username, password=password, timeout=10)
        logging.info(f"Connected to {ip}")
        return ssh
    except Exception as e:
        logging.error(f"Failed to connect to {ip}: {e}")
        return None

def execute_command(ssh, command):
    """Executes a command on the router and returns the output."""
    try:
        stdin, stdout, stderr = ssh.exec_command(command)
        output = stdout.read().decode().strip()
        error = stderr.read().decode().strip()
        if error:
            logging.warning(f"Command '{command}' stderr: {error}")
        return output
    except Exception as e:
        logging.error(f"Failed to execute '{command}': {e}")
        return ""

def find_interface(ssh, keyword):
    """Finds an interface name containing the keyword."""
    try:
        # Get list of VLAN interfaces
        output = execute_command(ssh, "/interface vlan print terse")
        
        # Regex to find interface name
        # Look for 'name=' followed by the interface name
        for line in output.splitlines():
            match = re.search(r'name=([^\s]+)', line)
            if match:
                if_name = match.group(1)
                if keyword.lower() in if_name.lower():
                    logging.info(f"Found interface for '{keyword}': {if_name}")
                    return if_name
        
        logging.warning(f"No interface found containing '{keyword}'")
        return None
    except Exception as e:
        logging.error(f"Error finding interface for '{keyword}': {e}")
        return None

def create_queue_type(ssh):
    """Creates the PCQ queue type 'GGC and FNA'."""
    cmd = '/queue type add name="GGC and FNA" kind=pcq pcq-rate=500M pcq-classifier=src-address,dst-address'
    
    # Check if exists first to avoid error
    check_cmd = '/queue type print where name="GGC and FNA"'
    existing = execute_command(ssh, check_cmd)
    
    if "GGC and FNA" not in existing:
        logging.info("Creating queue type 'GGC and FNA'")
        execute_command(ssh, cmd)
    else:
        logging.info("Queue type 'GGC and FNA' already exists.")

def create_simple_queue(ssh, name, target, dst, queue_type, comment):
    """Creates a simple queue and verifies creation."""
    cmd = f'/queue simple add name="{name}" target="{target}" dst="{dst}" max-limit=4G/4G queue="{queue_type}/{queue_type}" place-before=0 comment="{comment}"'
    
    # Check if exists
    check_cmd = f'/queue simple print where name="{name}"'
    existing = execute_command(ssh, check_cmd)
    
    if name in existing:
        logging.info(f"Simple queue '{name}' already exists. Updating max-limit to 4G/4G...")
        update_cmd = f'/queue simple set [find name="{name}"] max-limit=4G/4G'
        
        # Capture output of update
        update_output = execute_command(ssh, update_cmd)
        
        # Verify if update command returned an error (usually silent on success)
        if not update_output:
             logging.info(f"Successfully updated simple queue '{name}'")
             return True, "Updated successfully"
        else:
             msg = f"Failed to update simple queue '{name}'. Output: {update_output}"
             logging.error(msg)
             # We assume existence means partial success, but update failed. 
             # We return True for "queue exists" but log the error.
             return True, msg

    logging.info(f"Creating simple queue '{name}'")
    # Capture output to see if there are errors returned in stdout
    create_output = execute_command(ssh, cmd)
    
    # Verification
    existing_after = execute_command(ssh, check_cmd)
    
    if name in existing_after:
        logging.info(f"Successfully created simple queue '{name}'")
        return True, "Created successfully"
    else:
        msg = f"Failed to create simple queue '{name}'"
        if create_output:
             msg += f". Output: {create_output}"
        logging.error(msg)
        return False, msg

def main():
    input_file = 'routers.xlsx'
    error_report_file = 'error_report.csv'
    error_list = []

    try:
        df = pd.read_excel(input_file)
    except FileNotFoundError:
        logging.error(f"Input file '{input_file}' not found.")
        return

    for index, row in df.iterrows():
        ip = row['IP']
        username = row['Username']
        password = row['Password']
        
        logging.info(f"Processing Router: {ip}")
        
        ssh = connect_to_router(ip, username, password)
        if not ssh:
            error_list.append({'IP': ip, 'Error': 'Connection Failed'})
            continue
            
        try:
            # 1. Find Interfaces
            ggc_interface = find_interface(ssh, "GGC")
            fna_interface = find_interface(ssh, "FNA")
            
            # 2. Create Queue Type (Unified)
            create_queue_type(ssh)
            
            # 3. Create Simple Queue for GGC
            if ggc_interface:
                success, msg = create_simple_queue(
                    ssh, 
                    name="GGC-500", 
                    target="0.0.0.0/0", 
                    dst=ggc_interface, 
                    queue_type="GGC and FNA",
                    comment="GGC_500"
                )
                if not success:
                    error_list.append({'IP': ip, 'Error': f"GGC Queue: {msg}"})
            else:
                msg = "GGC Interface not found"
                logging.error(f"Skipping GGC queue creation for {ip}: {msg}")
                error_list.append({'IP': ip, 'Error': msg})

            # 4. Create Simple Queue for FNA
            if fna_interface:
                success, msg = create_simple_queue(
                    ssh, 
                    name="FNA-500", 
                    target="0.0.0.0/0", 
                    dst=fna_interface, 
                    queue_type="GGC and FNA",
                    comment="FNA_500"
                )
                if not success:
                    error_list.append({'IP': ip, 'Error': f"FNA Queue: {msg}"})
            else:
                msg = "FNA Interface not found"
                logging.error(f"Skipping FNA queue creation for {ip}: {msg}")
                error_list.append({'IP': ip, 'Error': msg})
                
        except Exception as e:
            msg = f"Unexpected Error: {str(e)}"
            logging.error(f"An unexpected error occurred for {ip}: {msg}")
            error_list.append({'IP': ip, 'Error': msg})
        finally:
            ssh.close()
            logging.info(f"Finished processing {ip}")
            print("-" * 30)

    # Save error report
    if error_list:
        error_df = pd.DataFrame(error_list)
        error_df.to_csv(error_report_file, index=False)
        print(f"\nErrors occurred. See '{error_report_file}' for details.")
    else:
        print("\nAll routers processed successfully without major errors.")

if __name__ == "__main__":
    main()
