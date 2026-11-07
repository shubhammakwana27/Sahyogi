"""Simple local launcher. Keys are entered privately and passed only to the app process."""
import argparse
import getpass
import os
from pathlib import Path
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parent
PROVIDERS = {
    "sarvam": ("Sarvam AI", "SARVAM_API_KEY", "SARVAM_MODEL", "sarvam-105b"),
    "gemini": ("Google Gemini", "GEMINI_API_KEY", "GEMINI_MODEL", "gemini-3.8-flash"),
    "openai": ("OpenAI", "OPENAI_API_KEY", "OPENAI_MODEL", ""),
}


def runtime_path(root):
    return root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def prepare_runtime(root, real_reader):
    runtime = runtime_path(root)
    if not runtime.is_file() and not real_reader:
        return sys.executable
    if not runtime.is_file():
        print("Creating the app's Python environment. Your saved cases will be kept.")
        venv.EnvBuilder(with_pip=True).create(root / ".venv")
    if real_reader:
        probe = ("from importlib.metadata import version; "
                 "assert version('crewai') == '1.15.30'; "
                 "version('google-genai'); version('openai')")
        installed = subprocess.run([str(runtime), "-c", probe], stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, check=False).returncode == 0
        if not installed:
            print("Installing the reader packages. This needs an internet connection and may take a few minutes.")
            subprocess.run([str(runtime), "-m", "pip", "install", "-r", str(root / "requirements.txt")], check=True)
    return str(runtime)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["demo", *PROVIDERS, "app"], help="Skip the provider menu")
    args = parser.parse_args(argv)
    print("SAHYOGI - palliative care questions and approved follow-up")
    print("Use made up details. The app saves your cases and sends no messages.")
    mode = args.mode
    if mode is None:
        print("1  Practise without an API key (offline sample rules)")
        print("2  Use Sarvam AI")
        print("3  Use Google Gemini")
        print("4  Use OpenAI")
        print("5  Enter or replace the API key inside the app")
        answer = input("Choose 1, 2, 3, 4 or 5 [1]: ").strip() or "1"
        mode = {"1": "demo", "2": "sarvam", "3": "gemini", "4": "openai", "5":"app"}.get(answer)
        if mode is None:
            print("Please run the launcher again and choose a listed option.")
            return 2
    env = os.environ.copy()
    in_app=mode=='app'
    if in_app:
        mode=env.get('SAHYOGI_PROVIDER','sarvam').strip().lower()
        if mode not in PROVIDERS:mode='sarvam'
    env["SAHYOGI_READER"] = "demo" if mode == "demo" else "crewai"
    if mode != "demo":
        if not (3, 10) <= sys.version_info[:2] < (3, 14):
            print("For the real CrewAI reader, use Python 3.10 to 3.13. Python 3.11 is shown in the manual.")
            return 2
        title, key_name, model_name, default_model = PROVIDERS[mode]
        env["SAHYOGI_PROVIDER"] = mode
        print(title + " selected. Reading a reply uses your provider's credits or quota.")
        key = env.get(key_name, "").strip()
        if not in_app and (not key or key.startswith("YOUR_")):
            key = getpass.getpass("Enter your API key (hidden): ").strip()
        if not in_app and (not key or key.startswith("YOUR_")):
            print("A real provider key is required. Choose offline practice if you do not have one.")
            return 2
        current_model = env.get(model_name, "").strip()
        if current_model.startswith("YOUR_"):
            current_model = ""
        model = current_model or default_model
        if not model and not in_app:
            model = input("Enter the exact supported model ID from your provider account: ").strip()
        if not model and not in_app:
            print("A model ID is required.")
            return 2
        env[key_name], env[model_name] = key, model
        print("The key is not saved to a file. Keep this terminal open while using the app.")
        if in_app:print('Sign in as the initial coordinator, open API settings, apply your key and test it there.')
    try:
        runtime = prepare_runtime(ROOT, mode != "demo")
        print("Open http://127.0.0.1:" + env.get("SAHYOGI_PORT", "8000") + " in your browser.")
        print("Sign in, then choose Simple guide for the question-first walkthrough. Press Ctrl+C to stop.")
        return subprocess.call([runtime, str(ROOT / "app.py")], cwd=ROOT, env=env)
    except (OSError, subprocess.CalledProcessError):
        print("Setup could not finish. Check Python, your internet connection and the setup section in the manual.")
        return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyboardInterrupt, EOFError):
        print("\nStopped. Existing saved cases are kept.")
