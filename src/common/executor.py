import subprocess
from typing import List, Optional


def execute_command(cmd: str) -> Optional[str]:
    """
    Executes a user command in a safe manner.
    Only allows predefined commands to prevent arbitrary code execution.
    
    Args:
        cmd (str): The command to execute.
    
    Returns:
        Optional[str]: The output of the command if successful, None otherwise.
    """
    allowed_commands = ['ls', 'pwd', 'whoami']  # Example allowed commands
    command_parts = cmd.split()
    
    if command_parts[0] not in allowed_commands:
        raise ValueError('Command not allowed')
    
    try:
        result = subprocess.run(command_parts, check=True, text=True, capture_output=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f'Error executing command: {e}')
        return None
    except Exception as e:
        print(f'Unexpected error: {e}')
        return None