import os
import sys
import json
import time
import tempfile
import shutil
import streamlit as st

st.set_page_config(page_title="Kaggle Runner", page_icon="🔗", layout="centered")

# ==========================================
# CONFIG
# ==========================================
KAGGLE_USERNAME = "thetuaiaa"
KAGGLE_KEY = "KGAT_c6aa2589e8c5ab869007668719aee16c" 
SLUG = "my-link-runner"
GPU_ENABLED = False

# Kaggle Library ကို အသစ်ဆုံး Version တင်ပါ (နောက်ကွယ်မှာ)
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
st.caption("One-Click Gradio Share Launcher")

# ==========================================
# KAGGLE SCRIPT
# ==========================================
KAGGLE_SCRIPT = r'''
import os, sys, time, re, shutil, subprocess
from importlib import metadata

REPO_URL = "https://github.com/Thetpaing467/new.git"
REPO_DIR = "/kaggle/working/new"
APP_FILE = "app.py"
PORT = 7860
LOG = "/kaggle/working/app.log"

def sh(cmd, timeout=600):
    try:
        p = subprocess.run(cmd, shell=True, text=True, capture_output=True, timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except Exception as e:
        return 1, str(e)

sh("pkill -f '[p]ython.*_gradio_share_wrapper.py'")
sh("pkill -f '[p]ython.*app.py'")
time.sleep(0.2)

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
    print("Installing missing packages: " + ", ".join(missing), flush=True)
    subprocess.run([sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "-q", *missing], capture_output=True, text=True)

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

print("Starting Gradio...", flush=True)
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
# PUSH FUNCTION (စောင့်စရာမလိုဘဲ ချက်ချင်း ပြီးမယ်)
# ==========================================
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

# ==========================================
# RUN
# ==========================================
def run():
    try:
        from kaggle.api.kaggle_api_extended import KaggleApi
        api = KaggleApi()
        api.authenticate()
        
        with st.spinner("Kaggle ကို လွှတ်လိုက်ပါပြီ..."):
            push_kernel(api)
            
        st.success("✅ အောင်မြင်ပါပြီ။ အောက်က ခလုတ်ကိုနှိပ်ပြီး Link ကို ယူပါ။")
        
    except Exception as e:
        st.error(f"Error: {e}")

# ==========================================
# BUTTONS
# ==========================================
if st.button("🚀 စတင်မယ်", type="primary", use_container_width=True):
    run()

st.divider()
st.markdown("### Link ယူရန် (၁ မိနစ်ခန့် စောင့်ပြီးမှ နှိပ်ပါ)")
st.markdown(f"[👉 ဒီနေရာကို နှိပ်ပြီး Kaggle Log ကြည့်မယ်](https://www.kaggle.com/code/{KAGGLE_USERNAME}/{SLUG}/log)")
st.caption("အပေါ်က Link ကို နှိပ်ပြီး Log ထဲမှာ `gradio.live` ပါတဲ့ Link ကို Copy ကူးပြီး ဖွင့်လိုက်ပါ။")