import os
import sys
import json
import time
import tempfile
import re
import shutil
import subprocess
import threading
import requests
import streamlit as st

from importlib import metadata

st.set_page_config(
    page_title="Kaggle Runner",
    page_icon="🔗",
    layout="centered",
)

# ==========================================
# CONFIG — မင်းရဲ့ Key များ တိုက်ရိုက်ထည့်ထားပါတယ်
# ==========================================
KAGGLE_USERNAME = "thetuaiaa"
KAGGLE_KEY = "KGAT_c6aa2589e8c5ab869007668719aee16c" 
TOPIC = "kgl-k-7f3a9c2e51b84d06"

# Kaggle Library ကို အသစ်ဆုံး Version တင်ပါ (နောက်ကွယ်မှာ)
os.system("pip install -U kaggle -q")

# Token အသစ်အတွက် kaggle.json ဖန်တီးပါ (401 Error မတက်အောင်)
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
LINK_TIMEOUT = 240

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
# KAGGLE SCRIPT
# ==========================================
KAGGLE_SCRIPT = r'''
import os, sys, time, re, json, shutil, subprocess
import threading
from importlib import metadata
import requests

NTFY_TOPIC = __TOPIC__
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
        p = subprocess.run(
            cmd, shell=True, text=True,
            capture_output=True, timeout=timeout
        )
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except Exception as e:
        return 1, str(e)

def read_log(n=8000):
    try:
        with open(LOG, "r", encoding="utf-8", errors="ignore") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size-n))
            return f.read()
    except Exception:
        return ""

def post(kind, message):
    try:
        r = requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=f"{kind}|{message}".encode("utf-8"),
            timeout=8,
        )
        r.raise_for_status()
    except Exception as e:
        say("ntfy error: " + str(e))

# Stop previous app
post("start", str(int(time.time())))
sh("pkill -f '[p]ython.*_gradio_share_wrapper.py'")
sh("pkill -f '[p]ython.*app.py'")
time.sleep(0.2)

RES = {}

# ==========================================
# Git
# ==========================================
def task_git():
    if os.path.isdir(os.path.join(REPO_DIR, ".git")):
        rc, out = sh(f"git -C {REPO_DIR} fetch -q origin")
        if rc == 0:
            rc, out = sh(
                f"git -C {REPO_DIR} reset -q --hard origin/HEAD"
            )
    else:
        if os.path.exists(REPO_DIR):
            shutil.rmtree(REPO_DIR)
        rc, out = sh(
            f"git clone -q --depth 1 {REPO_URL} {REPO_DIR}"
        )

    RES["git"] = (rc, out)
    say("git ready" if rc == 0 else "git failed: " + out[-500:])

# ==========================================
# Python dependencies
# ==========================================
def task_pip():
    required = {
        "gradio": "gradio>=5,<6",
        "faster-whisper": "faster-whisper",
        "edge-tts": "edge-tts",
        "gradio_client": "gradio_client",
        "yt-dlp": "yt-dlp",
        "gdown": "gdown",
        "opencv-python-headless": "opencv-python-headless",
        "pillow": "pillow",
        "requests": "requests",
        "numpy": "numpy",
    }

    missing = []

    for dist, spec in required.items():
        try:
            version = metadata.version(dist)
            if dist == "gradio" and not version.startswith("5."):
                missing.append(spec)
        except metadata.PackageNotFoundError:
            missing.append(spec)

    if not missing:
        RES["pip"] = True
        say("pip ready — already installed")
        return

    say("Installing missing packages: " + ", ".join(missing))

    try:
        p = subprocess.run(
            [
                sys.executable, "-m", "pip", "install",
                "--disable-pip-version-check", "-q", *missing
            ],
            capture_output=True, text=True, timeout=900
        )
        RES["pip"] = p.returncode == 0
        say(
            "pip ready" if p.returncode == 0
            else "pip failed: " + (p.stderr or p.stdout)[-800:]
        )
    except Exception as e:
        RES["pip"] = False
        say("pip error: " + str(e))

# ==========================================
# System dependencies
# ==========================================
def task_apt():
    packages = [
        "ffmpeg", "libraqm0", "libfribidi0",
        "fonts-noto-core", "fonts-noto-cjk",
        "fonts-dejavu-core", "fonts-sil-padauk"
    ]

    missing = []
    for package in packages:
        rc, out = sh(
            f"dpkg-query -W -f='${{Status}}' {package}"
        )
        if rc != 0 or "install ok installed" not in out:
            missing.append(package)

    if not missing:
        RES["apt"] = True
        say("apt ready — already installed")
        return

    cmd = (
        "DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "
        "--no-install-recommends " + " ".join(missing)
    )
    rc, out = sh(cmd)

    if rc != 0:
        sh("apt-get update -qq")
        rc, out = sh(cmd)

    RES["apt"] = rc == 0
    say("apt ready" if rc == 0 else "apt failed: " + out[-500:])

# Start preparation tasks concurrently
tasks = [
    threading.Thread(target=task_git),
    threading.Thread(target=task_pip),
    threading.Thread(target=task_apt),
]

for t in tasks:
    t.start()
for t in tasks:
    t.join()

if RES.get("git", (1, ""))[0] != 0:
    post("error", "Git failed: " + RES["git"][1][-300:])
    raise SystemExit("Git clone/update failed")

if not RES.get("pip", False):
    post("error", "Python package installation failed")
    raise SystemExit("pip installation failed")

if not RES.get("apt", False):
    say("WARNING: Some system packages failed")

# ==========================================
# App configuration
# ==========================================
os.chdir(REPO_DIR)

if not os.path.isfile(APP_FILE):
    post("error", "app.py repo ထဲမှာ မရှိပါ")
    raise SystemExit("app.py not found")

fonts = [
    f for f in os.listdir(".")
    if f.lower().endswith((".ttf", ".otf", ".ttc"))
]
if fonts:
    preferred = "MyanmarPadaung.ttf"
    os.environ["RECAP_FONT"] = os.path.abspath(
        preferred if preferred in fonts else sorted(fonts)[0]
    )

os.environ["GRADIO_ANALYTICS_ENABLED"] = "False"
os.environ["PYTHONUNBUFFERED"] = "1"

# ==========================================
# Gradio wrapper
# ==========================================
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

# ==========================================
# Launch and detect URL
# ==========================================
say("Starting Gradio...")

log_file = open(LOG, "w", encoding="utf-8")
env = os.environ.copy()
env["PORT"] = str(PORT)

app_proc = subprocess.Popen(
    [sys.executable, "-u", "_gradio_share_wrapper.py"],
    stdout=log_file,
    stderr=subprocess.STDOUT,
    env=env,
)

share_url = None
deadline = time.monotonic() + 240
log_pos = 0
log_buffer = ""

try:
    while time.monotonic() < deadline:
        if app_proc.poll() is not None:
            log_file.flush()
            output = read_log()
            print(output, flush=True)
            post("error", "App crashed: " + output[-300:])
            break

        try:
            log_file.flush()
            with open(LOG, "r", encoding="utf-8", errors="ignore") as f:
                f.seek(log_pos)
                chunk = f.read()
                log_pos = f.tell()

            if chunk:
                log_buffer = (log_buffer + chunk)[-20000:]
                match = re.search(
                    r"https://[a-zA-Z0-9-]+\.gradio\.live",
                    log_buffer
                )
                if match:
                    share_url = match.group(0)
                    break
        except (OSError, ValueError) as e:
            say("Log read error: " + str(e))

        time.sleep(0.25)

    if share_url:
        say("Gradio URL ready")
        post("cloudflare", share_url)
        post("ready", "1")
        print("GRADIO_SHARE_URL=" + share_url, flush=True)

        while app_proc.poll() is None:
            time.sleep(5)

        say("App stopped: " + str(app_proc.returncode))
        print(read_log(), flush=True)

    else:
        output = read_log()
        print("Share URL timeout/crash", flush=True)
        print(output, flush=True)
        post("error", "Share URL timeout: " + output[-300:])

        if app_proc.poll() is None:
            app_proc.terminate()
            try:
                app_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                app_proc.kill()

        raise SystemExit("Gradio URL was not detected")

finally:
    if app_proc.poll() is None:
        app_proc.terminate()
    log_file.close()
'''

# ==========================================
# KAGGLE / NTFY
# ==========================================
def read_state(since_time=0):
    ready, error, link = False, None, None

    try:
        params = {"poll": "1"}
        if since_time:
            params["since"] = str(max(0, int(since_time)))

        r = requests.get(
            f"https://ntfy.sh/{TOPIC}/json",
            params=params,
            timeout=8,
        )
        r.raise_for_status()

        for line in r.text.splitlines():
            try:
                d = json.loads(line)
            except (ValueError, TypeError):
                continue

            if d.get("event") != "message":
                continue

            msg = d.get("message", "")
            if "|" not in msg:
                continue

            kind, value = msg.split("|", 1)

            if kind == "start":
                ready, error, link = False, None, None
            elif kind == "cloudflare":
                link = value
            elif kind == "ready":
                ready = True
            elif kind == "error":
                error = value

    except Exception:
        pass

    return ready, error, link


def kernel_busy(api):
    try:
        result = api.kernels_status(f"{KAGGLE_USERNAME}/{SLUG}")
        status = str(getattr(result, "status", result)).lower()
        return "running" in status or "queued" in status
    except Exception:
        return False


def push_kernel(api):
    code = KAGGLE_SCRIPT.replace("__TOPIC__", json.dumps(TOPIC))
    folder = tempfile.mkdtemp(prefix="kaggle_runner_")

    try:
        with open(
            os.path.join(folder, "script.py"), "w", encoding="utf-8"
        ) as f:
            f.write(code)

        meta = {
            "id": f"{KAGGLE_USERNAME}/{SLUG}",
            "title": SLUG,
            "code_file": "script.py",
            "language": "python",
            "kernel_type": "script",
            "is_private": "true",
            "enable_gpu": "true" if GPU_ENABLED else "false",
            "enable_internet": "true",
        }

        with open(
            os.path.join(folder, "kernel-metadata.json"), "w"
        ) as f:
            json.dump(meta, f)

        api.kernels_push(folder)

    finally:
        shutil.rmtree(folder, ignore_errors=True)


def show_link(url):
    st.success("Gradio Link အဆင်သင့်ဖြစ်ပြီ")
    st.link_button("🔗 ဖွင့်မယ်", url, use_container_width=True)
    st.code(url, language=None)


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

        if kernel_busy(api) and not force:
            status.info("Kaggle kernel run နေပြီးသားဖြစ်လို့ Link စစ်နေတယ်...")
            ready, error, link = read_state()

            if ready and link:
                progress.progress(100)
                status.success("Link ရပါပြီ")
                show_link(link)
            elif error:
                status.error(error)
            else:
                status.warning(
                    "Kernel run နေပါတယ်။ Link မရသေးရင် "
                    "Kaggle Logs ကိုစစ်ပါ၊ သို့မဟုတ် ပြန်စမယ်ကိုနှိပ်ပါ။"
                )
            return

        # Publish start marker before pushing the new run
        started_at = int(time.time())
        requests.post(
            f"https://ntfy.sh/{TOPIC}",
            data=f"start|{started_at}".encode(),
            timeout=8,
        )

        status.info("Kaggle kernel push လုပ်နေတယ်...")
        progress.progress(10)
        push_kernel(api)

        status.info("Gradio Link စောင့်နေတယ်...")
        deadline = time.monotonic() + LINK_TIMEOUT

        while time.monotonic() < deadline:
            ready, error, link = read_state(since_time=started_at)

            if error:
                status.error("Kaggle app error")
                st.error(error)
                return

            if ready and link:
                progress.progress(100)
                status.success("အဆင်သင့်ဖြစ်ပြီ")
                show_link(link)
                return

            time.sleep(1)

        status.error("Link စောင့်ဆိုင်းချိန်ကုန်သွားပြီ")
        st.warning(
            "Kaggle → Code → my-link-runner → Logs ကိုစစ်ပါ။ "
            "Share URL မထွက်ရင် app.log ထဲက error ကိုကြည့်ပါ။"
        )

    except Exception as e:
        status.error("Run မအောင်မြင်ပါ")
        st.exception(e)


# ==========================================
# BUTTONS
# ==========================================
c1, c2 = st.columns(2)

with c1:
    start = st.button(
        "🚀 စတင်မယ်",
        type="primary",
        use_container_width=True,
    )

with c2:
    restart = st.button(
        "🔄 ပြန်စမယ်",
        use_container_width=True,
    )

if start:
    run(force=False)
elif restart:
    run(force=True)