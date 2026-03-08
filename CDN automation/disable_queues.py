import pandas as pd
import paramiko
import logging
import socket

# Configure logging
logging.basicConfig(
    filename='disable_queues.log',
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

def disable_queue(ssh, comment):
    """Disables a simple queue found by its comment."""
    cmd = f'/queue simple disable [find comment="{comment}"]'
    logging.info(f"Disabling queue with comment '{comment}'...")
    execute_command(ssh, cmd)

def main():
    input_file = 'routers.xlsx'
    
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
            continue
            
        try:
            # Disable GGC Queue
            disable_queue(ssh, "GGC_500")
            
            # Disable FNA Queue
            disable_queue(ssh, "FNA_500")
                
        except Exception as e:
            logging.error(f"An unexpected error occurred for {ip}: {e}")
        finally:
            ssh.close()
            logging.info(f"Finished processing {ip}")
            print("-" * 30)

if __name__ == "__main__":
    main()
