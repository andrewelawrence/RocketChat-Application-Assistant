# load_envs.py
import sys, subprocess

def parse_env_file(file_path="config/.env"):
    env_vars = {}
    with open(file_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                key, val = line.split("=", 1)
                env_vars[key] = val.strip().strip('"').strip("'")
    return env_vars

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: run.sh <script.py> [script args...]")
        sys.exit(1)
        
    script = sys.argv[1]
    script_args = sys.argv[2:]

    envs = parse_env_file()
    exports = " && ".join([f'export {k}="{v}"' for k,v in envs.items()])
    
    cmd = f"{exports} && python {script}"
    if script_args:
        cmd += " " + " ".join(script_args)

    subprocess.run(cmd, shell=True)
    