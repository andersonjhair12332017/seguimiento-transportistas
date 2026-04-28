import subprocess
import sys


def run(cmd):
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    # Migraciones
    run([sys.executable, "manage.py", "migrate"])

    # Datos base
    run([sys.executable, "manage.py", "seed_base"])

    # Usuarios operativos por área
    run([sys.executable, "manage.py", "seed_usuarios_area"])
