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

# Note: keep the script as a arg because it must be run as a process in the
# shell created below to have access to the envs.
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Something went wrong: len(sys.argv) < 2 but test.sh sets len(sys.argv) = 2.")
        
    script = sys.argv[1]

    print("Loading Environment variables...")
    envs = parse_env_file()
    exports = " && ".join([f'export {k}="{v}"' for k,v in envs.items()])
    
    cmd = f"{exports} && python {script}"

    print(f"Flask app loading onto http://{envs["flaskHost"]}:{envs["flaskPort"]}/{envs["flaskEnv"]}...")
    subprocess.run(cmd, shell=True)
    