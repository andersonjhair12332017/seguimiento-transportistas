import subprocess
import sys


def run(cmd):
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    run([sys.executable, "manage.py", "migrate"])
    run([sys.executable, "manage.py", "seed_base"])