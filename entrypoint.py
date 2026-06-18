import subprocess
import sys

# KiCad entrypoint does not allow to use 'python -m' directly
# and accepts script only, thus we need this intermediate file
cmd = [sys.executable, "-m", "via_patterns"]
cmd += sys.argv[1:]
result = subprocess.run(cmd)
sys.exit(result.returncode)
