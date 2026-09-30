"""
Build and packaging script for KRT Bookings Tracker Agent.
Compiles standalone single-file binary with PyInstaller.
Bakes environment configurations into the binary for clean client-side execution.
"""
import os
import sys
import subprocess
from pathlib import Path


def load_env_file(root_dir: Path):
    """Loads key-value pairs from .env into os.environ if present."""
    env_path = root_dir / ".env"
    if env_path.exists():
        print("[Build] Loading local .env file...")
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("'\"")
                    if k not in os.environ:
                        os.environ[k] = v


def generate_build_config(root_dir: Path) -> Path:
    """Generates a temporary baked config module to embed secrets in the binary."""
    config_file = root_dir / "agent" / "_build_config.py"
    supabase_url = os.environ.get("SUPABASE_URL", "")
    supabase_anon_key = os.environ.get("SUPABASE_ANON_KEY", "")
    github_repo = os.environ.get("GITHUB_REPO", "krt-bookings/krt-bookings-tracker")

    content = f'''"""
Auto-generated baked build config.
"""
BAKED_CONFIG = {{
    "SUPABASE_URL": "{supabase_url}",
    "SUPABASE_ANON_KEY": "{supabase_anon_key}",
    "GITHUB_REPO": "{github_repo}",
}}
'''
    config_file.write_text(content, encoding="utf-8")
    print(f"[Build] Generated embedded config in {config_file.name}")
    return config_file


def build_executable():
    root_dir = Path(__file__).parent.resolve()
    icon_ico = root_dir / "assets" / "app_icon.ico"
    icon_png = root_dir / "assets" / "app_icon.png"

    # 1. Load env
    load_env_file(root_dir)

    # 2. Make sure icons exist
    if not icon_ico.exists() or not icon_png.exists():
        print("[Build] Generating icons...")
        from generate_assets import generate_icons
        generate_icons()

    # 3. Bake environment config for compilation
    baked_file = generate_build_config(root_dir)

    print("[Build] Running PyInstaller compilation...")

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconsole",
        "--onefile",
        "--name", "KRT-Bookings-Tracker",
        "--clean",
        f"--add-data={root_dir / 'assets'}{os.pathsep}assets",
        "--hidden-import=pystray._win32" if sys.platform == "win32" else "--hidden-import=pystray._util",
        "--hidden-import=cryptography",
        "--hidden-import=requests",
        "--hidden-import=PIL",
        "--hidden-import=tkinter",
    ]

    if sys.platform == "win32" and icon_ico.exists():
        cmd.extend(["--icon", str(icon_ico)])

    cmd.append(str(root_dir / "main.py"))

    print(f"[Build] Command: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, cwd=root_dir)

        if result.returncode == 0:
            dist_dir = root_dir / "dist"
            print(f"\n[Build] SUCCESS! Executable built in: {dist_dir}")
            for file in dist_dir.glob("*"):
                print(f" -> {file.name} ({file.stat().st_size / (1024*1024):.2f} MB)")
        else:
            print(f"\n[Build] FAILED with return code: {result.returncode}")
            sys.exit(result.returncode)
    finally:
        # Cleanup temporary baked config after compilation
        if baked_file.exists():
            baked_file.unlink()
            print("[Build] Cleaned up temporary _build_config.py.")


if __name__ == "__main__":
    build_executable()
