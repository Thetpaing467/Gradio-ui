import os
import sys
import json
import time
import tempfile
import re
import shutil
import subprocess
import requests
import streamlit as st
from importlib import metadata

st.set_page_config(page_title="Kaggle Runner", page_icon="🔗", layout="centered")

# ==========================================
# CONFIG
# ==========================================
KAGGLE_USERNAME = "thetuaiaa"
KAGGLE_KEY = "KGAT_c6aa2589e8c5ab869007668719aee16c" 

# Kaggle Library ကို အသစ်ဆုံး Version တင်ပါ
os.system("pip install -U kaggle -q")

# Token အသစ်အတွက် kaggle.json ဖန်တီးပါ
kaggle_cred = {"username": KAGGLE_USERNAME, "key": KAGGLE_KEY}
os.makedirs(os.path.expanduser("~/.kaggle"), exist_ok=True)
with open(os.path.expanduser("~/.kaggle/kaggle.json"), "w") as f:
    json.dump(kaggle_cred, f)
os.chmod(os.path.expanduser("~/.kaggle/kaggle.json"), 0o600)

os.environ["KAGGLE_USERNAME"] = KAGGLE_USERNAME
os.environ["KAGGLE_KEY"] = KAGGLE_KEY
os.environ["KAGGLE_API_TOKEN"] = KAGGLE_KEY

SLUG = "my-link-runner"
GPU_ENABLED = False
LINK_TIMEOUT = 300 # ၅ မိနစ် စောင့်မယ်

# ==========================================
# UI
# ==========================================
st.markdown("""
<style>
#MainMenu, footer, header {visibility:hidden;}
.block-container {max-width:520px;padding-top:3rem;}
.stButton>button,.stLinkButton>a {
    height:3.2rem;border-radius:12px;font-weight:600;
}
h1 {text-align:center;font-size:1.7rem!important;}
</style>
""", unsafe_allow_html=True)

st.title("🔗 Kaggle Runner")
st.caption("Fast Gradio Share Launcher")

# ==========================================
# KAGGLE SCRIPT (ntfy ဖြုတ်ထားပါတယ်)
# ==========================================
KAGGLE_SCRIPT = r'''
import os, sys, time, re, json, shutil, subprocess
from importlib import metadata

REPO_URL = "https://github.com/Thetpaing467/new.git"
REPO_DIR = "/kaggle/working/new"
APP_FILE = "app.py"
PORT = 7860
LOG = "/kaggle/working/app.log"
T0 = time.monotonic()

def say(msg):
    print(f"[{time.monotonic()-T0:6.1f}s] {msg}", flush=True)

def sh(cmd, timeout=600):
    try:
        p = subprocess.run(cmd, shell=True, text=True, capture_output=True, timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except Exception as e:
        return 1, str(e)

# Stop previous app
sh("pkill -f '[p]ython.*_gradio_share_wrapper.py'")
sh("pkill -f '[p]ython.*app.py'")
time.sleep(0.2)

# Git Clone
if os.path.isdir(os.path.join(REPO_DIR, ".git")):
    rc, out = sh(f"git -C {REPO_DIR} fetch -q origin")
    if rc == 0:
        rc, out = sh(f"git -C {REPO_DIR} reset -q --hard origin/HEAD")
else:
    if os.path.exists(REPO_DIR):
        shutil.rmtree(REPO_DIR)
    rc, out = sh(f"git clone -q --depth 1 {REPO_URL} {REPO_DIR}")

if rc != 0:
    print("Git failed: " + out[-300:], flush=True)
    raise SystemExit(1)

# Pip Install
required = {
    "gradio": "gradio>=5,<6", "faster-whisper": "faster-whisper",
    "edge-tts": "edge-tts", "gradio_client": "gradio_client",
    "yt-dlp": "yt-dlp", "gdown": "gdown", "opencv-python-headless": "opencv-python-headless",
    "pillow": "pillow", "requests": "requests", "numpy": "numpy",
}
missing = []
for dist, spec in required.items():
    try:
        version = metadata.version(dist)
        if dist == "gradio" and not version.startswith("5."):
            missing.append(spec)
    except metadata.PackageNotFoundError:
        missing.append(spec)

if missing:
    say("Installing missing packages: " + ", ".join(missing))
    subprocess.run([sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "-q", *missing], capture_output=True, text=True)

# App config
os.chdir(REPO_DIR)
fonts = [f for f in os.listdir(".") if f.lower().endswith((".ttf", ".otf", ".ttc"))]
if fonts:
    preferred = "MyanmarPadaung.ttf"
    os.environ["RECAP_FONT"] = os.path.abspath(preferred if preferred in fonts else sorted(fonts)[0])

os.environ["GRADIO_ANALYTICS_ENABLED"] = "False"
os.environ["PYTHONUNBUFFERED"] = "1"

WRAPPER = r"""
import sys, runpy, gradio
_original_launch = gradio.Blocks.launch
def _patched_launch(self, *args, **kwargs):
    kwargs["share"] = True
    kwargs["server_name"] = "0.0.0.0"
    kwargs["server_port"] = 7860
    kwargs["show_error"] = True
    return _original_launch(self, *args, **kwargs)
gradio.Blocks.launch = _patched_launch
sys.argv = ["app.py"]
runpy.run_path("app.py", run_name="__main__")
"""

with open("_gradio_share_wrapper.py", "w", encoding="utf-8") as f:
    f.write(WRAPPER)

say("Starting Gradio...")
log_file = open(LOG, "w", encoding="utf-8")
app_proc = subprocess.Popen([sys.executable, "-u", "_gradio_share_wrapper.py"], stdout=log_file, stderr=subprocess.STDOUT)

share_url = None
deadline = time.monotonic() + 240
log_pos = 0
log_buffer = ""

try:
    while time.monotonic() < deadline:
        if app_proc.poll() is not None:
            log_file.flush()
            print("App crashed", flush=True)
            break

        try:
            log_file.flush()
            with open(LOG, "r", encoding="utf-8", errors="ignore") as f:
                f.seek(log_pos)
                chunk = f.read()
                log_pos = f.tell()
            if chunk:
                log_buffer = (log_buffer + chunk)[-20000:]
                match = re.search(r"https://[a-zA-Z0-9-]+\.gradio\.live", log_buffer)
                if match:
                    share_url = match.group(0)
                    break
        except Exception:
            pass
        time.sleep(0.25)

    if share_url:
        print("GRADIO_SHARE_URL=" + share_url, flush=True)
        while app_proc.poll() is None:
            time.sleep(5)
    else:
        print("Share URL timeout", flush=True)
        if app_proc.poll() is None:
            app_proc.terminate()
        raise SystemExit("Gradio URL was not detected")
finally:
    if app_proc.poll() is None:
        app_proc.terminate()
    log_file.close()
'''

# ==========================================
# HELPERS
# ==========================================
def kernel_busy(api):
    try:
        result = api.kernels_status(f"{KAGGLE_USERNAME}/{SLUG}")
        status = str(getattr(result, "status", result)).lower()
        return "running" in status or "queued" in status
    except Exception:
        return False

def push_kernel(api):
    folder = tempfile.mkdtemp(prefix="kaggle_runner_")
    try:
        with open(os.path.join(folder, "script.py"), "w", encoding="utf-8") as f:
            f.write(KAGGLE_SCRIPT)
        meta = {
            "id": f"{KAGGLE_USERNAME}/{SLUG}", "title": SLUG, "code_file": "script.py",
            "language": "python", "kernel_type": "script", "is_private": "true",
            "enable_gpu": "true" if GPU_ENABLED else "false", "enable_internet": "true",
        }
        with open(os.path.join(folder, "kernel-metadata.json"), "w") as f:
            json.dump(meta, f)
        api.kernels_push(folder)
    finally:
        shutil.rmtree(folder, ignore_errors=True)

def show_link(url):
    st.success("Gradio Link အဆင်သင့်ဖြစ်ပြီ")
    st.link_button("🔗 ဖွင့်မယ်", url, use_container_width=True)
    st.code(url, language=None)

# ==========================================
# MAIN RUN FUNCTION
# ==========================================
def run(force=False):
    try:
        from kaggle.api.kaggle_api_extended import KaggleApi
    except Exception as e:
        st.error(f"Kaggle package error: {e}")
        return

    progress = st.progress(0)
    status = st.empty()

    try:
        status.info("Kaggle login စစ်ဆေးနေတယ်...")
        api = KaggleApi()
        api.authenticate()
        progress.progress(5)

        status.info("Kaggle kernel push လုပ်နေတယ်... (ခဏစောင့်ပါ)")
        progress.progress(10)
        push_kernel(api)

        status.info("Link ထွက်လာတာကို စောင့်နေတယ်... (၃-၅ မိနစ်ကြာနိုင်ပါတယ်)")
        deadline = time.monotonic() + LINK_TIMEOUT
        found_link = None

        # Kaggle Output ထဲက Link ကို တိုက်ရိုက်ရှာမယ်
        while time.monotonic() < deadline:
            try:
                # kernel output ကို ဖတ်မယ်
                files = api.kernels_output(f"{KAGGLE_USERNAME}/{SLUG}")
                if files:
                    for f in files:
                        if "script.log" in f or "output.log" in f or ".log" in f:
                            with open(f, "r", encoding="utf-8", errors="ignore") as log_f:
                                content = log_f.read()
                                match = re.search(r"https://[a-zA-Z0-9-]+\.gradio\.live", content)
                                if match:
                                    found_link = match.group(0)
                                    break
                if found_link:
                    break
            except Exception as e:
                pass # Kernel မပြီးသေးရင် Error တက်တတ်လို့ ignore လုပ်မယ်

            time.sleep(5)

        if found_link:
            progress.progress(100)
            status.success("အဆင်သင့်ဖြစ်ပြီ")
            show_link(found_link)
        else:
            status.error("Link စောင့်ဆိုင်းချိန်ကုန်သွားပြီ")
            st.warning("Kaggle → Code → my-link-runner → Logs ကိုစစ်ပါ။ Link ထွက်ဖို့ အချိန်ပိုကြာနိုင်ပါတယ်။ ခဏနေပြီး Logs မှာ ပြန်စစ်ကြည့်ပါ။")

    except Exception as e:
        status.error("Run မအောင်မြင်ပါ")
        st.exception(e)

# ==========================================
# BUTTONS
# ==========================================
c1, c2 = st.columns(2)
with c1:
    start = st.button("🚀 စတင်မယ်", type="primary", use_container_width=True)
with c2:
    restart = st.button("🔄 ပြန်စမယ်", use_container_width=True)

if start:
    run(force=False)
elif restart:
    run(force=True)