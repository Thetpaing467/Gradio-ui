import os, json, time, tempfile
import requests
import streamlit as st

# ==========================================
# Settings  (Streamlit Secrets)
#   KAGGLE_USERNAME = "thetuaiaa"
#   KAGGLE_KEY      = "kgl-k-7f3a9c2e51b84d06"
#   CF_TUNNEL_TOKEN = "eyJhIjoiYTQ1N2IxODU1Y2FlMzYwNGQ3NGVlYzY0YjJkNmIxNjgiLCJ0IjoiN2UxYjFkZTAtMTIyYy00YWYzLWFlMGItM2VhMTU2ZGI3NzI5IiwicyI6Ik5tTTFOakJsT1dZdE0yVXhZaTAwWWpFeUxUazVNVFl0TXpFd04yRTBaR1ZqWTJNMCJ9"
# ==========================================
KAGGLE_USERNAME = st.secrets.get("KAGGLE_USERNAME", os.environ.get("KAGGLE_USERNAME", "thetuaiaa"))
KAGGLE_KEY = st.secrets.get("KAGGLE_KEY", os.environ.get("KAGGLE_KEY", ""))
CF_TOKEN = st.secrets.get("CF_TUNNEL_TOKEN", os.environ.get("CF_TUNNEL_TOKEN", ""))
DOMAIN_URL = "https://tpokemb.dpdns.org"
SLUG = "my-link-runner"
GPU_ENABLED = False
TOPIC = "kgl-k-7f3a9c2e51b84d06"

os.environ["KAGGLE_USERNAME"] = KAGGLE_USERNAME
os.environ["KAGGLE_KEY"] = KAGGLE_KEY
from kaggle.api.kaggle_api_extended import KaggleApi

st.set_page_config(page_title="Kaggle Runner", page_icon="🔗", layout="centered")

st.markdown(
    """
    <style>
    #MainMenu, footer, header {visibility: hidden;}
    .block-container {max-width: 520px; padding-top: 3rem;}
    .stButton > button, .stLinkButton > a {
        height: 3.2rem; border-radius: 12px; font-weight: 600;
    }
    h1 {text-align: center; font-size: 1.7rem !important; margin-bottom: 1.5rem;}
    </style>
    """,
    unsafe_allow_html=True,
)

# ==========================================
# Kaggle မှာ Run မယ့် Script
# ==========================================
KAGGLE_SCRIPT = r'''
import os, re, sys, time, subprocess, threading
from importlib import metadata
import requests

NTFY_TOPIC = "__TOPIC__"
REPO_URL = "https://github.com/Thetpaing467/new.git"
REPO_DIR = "/kaggle/working/new"
APP_FILE = "app.py"
PORT = 7860
LOG = "/kaggle/working/app.log"
CF_LOG = "/kaggle/working/cf.log"
CF_BIN = "/kaggle/working/cloudflared"
CF_TOKEN = "__CFTOKEN__"
DOMAIN_URL = "__URL__"
T0 = time.time()

def say(msg):
    print(f"[{time.time() - T0:5.1f}s] {msg}", flush=True)

def sh(cmd):
    p = subprocess.run(cmd, shell=True, text=True, capture_output=True)
    return p.returncode, (p.stdout + p.stderr)

def read(path, n=3000):
    try:
        return open(path, encoding="utf-8", errors="ignore").read()[-n:]
    except Exception:
        return ""

def post(kind, text):
    try:
        requests.post(f"https://ntfy.sh/{NTFY_TOPIC}",
                      data=f"{kind}|{text}".encode("utf-8"), timeout=15)
    except Exception as e:
        print("ntfy error:", e)

post("start", "1")
sh("pkill -f '[p]ython.*app.py'")
sh("pkill -f '[c]loudflared'")
time.sleep(0.3)

RES = {}

def task_git():
    if os.path.exists(REPO_DIR):
        rc, out = sh(f"cd {REPO_DIR} && git fetch -q origin && git reset -q --hard origin/HEAD")
    else:
        rc, out = sh(f"git clone -q --depth 1 {REPO_URL} {REPO_DIR}")
    RES["git"] = (rc, out)
    say("git ✅" if rc == 0 else f"git ❌ {out[-300:]}")

def task_pip():
    need = {
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
    for dist, spec in need.items():
        try:
            v = metadata.version(dist)
            if dist == "gradio" and not v.startswith("5."):
                missing.append(spec)
        except metadata.PackageNotFoundError:
            missing.append(spec)
    if missing:
        say(f"pip install: {', '.join(missing)}")
        quoted = " ".join(f"'{m}'" for m in missing)
        rc, out = sh(f"{sys.executable} -m pip install -q {quoted}")
        if rc != 0:
            say(f"pip ❌ {out[-500:]}")
    RES["pip"] = True
    say("pip ✅")

def task_apt():
    need = ["ffmpeg", "libraqm0", "libfribidi0", "fonts-noto-core", "fonts-noto-cjk",
            "fonts-dejavu-core", "fonts-sil-padauk"]
    missing = [p for p in need if sh(f"dpkg -s {p}")[0] != 0]
    if missing:
        say(f"apt install: {', '.join(missing)}")
        cmd = ("DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "
               f"--no-install-recommends {' '.join(missing)}")
        rc, _ = sh(cmd)
        if rc != 0:
            sh("apt-get update -qq")
            sh(cmd)
    RES["apt"] = True
    say("apt ✅")

def task_cf():
    if os.path.exists(CF_BIN):
        RES["cf"] = True
        return
    rc, out = sh("curl -sL -o " + CF_BIN +
                 " https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
                 " && chmod +x " + CF_BIN)
    RES["cf"] = (rc == 0)
    say("cloudflared ✅" if rc == 0 else f"cloudflared ❌ {out[-300:]}")

threads = [threading.Thread(target=f) for f in (task_git, task_pip, task_apt, task_cf)]
for t in threads:
    t.start()
threads[0].join()
threads[1].join()
threads[3].join()

if RES.get("git", (1,))[0] != 0:
    post("error", "git clone/update မအောင်မြင်ပါ: " + RES["git"][1][-300:])
    raise SystemExit("git မအောင်မြင်ပါ")
if not RES.get("cf"):
    post("error", "cloudflared download မအောင်မြင်ပါ")
    raise SystemExit("cloudflared မအောင်မြင်ပါ")

os.chdir(REPO_DIR)
if not os.path.exists(APP_FILE):
    post("error", "app.py repo ထဲမှာ မရှိပါ")
    raise SystemExit("app.py မရှိပါ")

fonts = [f for f in os.listdir(".") if f.lower().endswith((".ttf", ".otf", ".ttc"))]
if fonts:
    os.environ["RECAP_FONT"] = os.path.abspath(
        "MyanmarPadaung.ttf" if "MyanmarPadaung.ttf" in fonts else sorted(fonts)[0])
os.environ["GRADIO_ANALYTICS_ENABLED"] = "False"

WRAPPER = """
import runpy, gradio, sys

_original_launch = gradio.Blocks.launch
def _patched_launch(self, *args, **kwargs):
    kwargs['share'] = False
    kwargs['server_name'] = '0.0.0.0'
    kwargs['server_port'] = 7860
    return _original_launch(self, *args, **kwargs)
gradio.Blocks.launch = _patched_launch

sys.argv = ["app.py"]
runpy.run_path("app.py", run_name="__main__")
"""
with open("_gradio_share_wrapper.py", "w") as f:
    f.write(WRAPPER)

env = dict(os.environ, PORT=str(PORT))
app_proc = subprocess.Popen([sys.executable, "-u", "_gradio_share_wrapper.py"],
                            stdout=open(LOG, "w"), stderr=subprocess.STDOUT, env=env)
say("app စတင်နေတယ်...")

cf_proc = subprocess.Popen([CF_BIN, "tunnel", "--no-autoupdate", "run", "--token", CF_TOKEN],
                           stdout=open(CF_LOG, "w"), stderr=subprocess.STDOUT)
say("cloudflared စတင်နေတယ်...")

app_ok = False
cf_ok = False
ready = False

for _ in range(1200):
    if app_proc.poll() is not None:
        print(f"❌ App crash (exit {app_proc.returncode})")
        print(read(LOG))
        post("error", "App crash: " + read(LOG, 400))
        break
    if cf_proc.poll() is not None:
        print("❌ cloudflared ရပ်သွားတယ်")
        print(read(CF_LOG))
        post("error", "Tunnel error: " + read(CF_LOG, 400))
        break

    if not app_ok:
        try:
            app_ok = requests.get(f"http://127.0.0.1:{PORT}", timeout=2).status_code == 200
            if app_ok:
                say("app ✅")
        except Exception:
            pass

    if not cf_ok and "Registered tunnel connection" in read(CF_LOG, 20000):
        cf_ok = True
        say("tunnel ✅")

    if app_ok and cf_ok:
        post("cloudflare", DOMAIN_URL)
        post("ready", "1")
        ready = True
        say(f"ready ✅ {DOMAIN_URL}")
        break

    time.sleep(0.5)

if not ready:
    print("⚠️ မအောင်မြင်ပါ — log:\n")
    print(read(LOG))
    print(read(CF_LOG))
    post("error", "Start မအောင်မြင်ပါ: " + read(LOG, 200) + read(CF_LOG, 200))
    raise SystemExit("ရပ်လိုက်တယ်။")

print(f"Running... log: {LOG}")
while True:
    time.sleep(30)
    if app_proc.poll() is not None:
        print(f"❌ App ရပ်သွားပြီ (exit {app_proc.returncode}) — log:\n")
        print(read(LOG))
        break
'''

# ==========================================
# Helpers
# ==========================================
def read_state():
    ready, error, start_t = False, None, 0
    try:
        r = requests.get(f"https://ntfy.sh/{TOPIC}/json?poll=1&since=all", timeout=10)
        for line in r.text.strip().splitlines():
            try:
                d = json.loads(line)
            except Exception:
                continue
            if d.get("event") != "message":
                continue
            msg = d.get("message", "")
            if "|" not in msg:
                continue
            kind, val = msg.split("|", 1)
            if kind == "start":
                ready, error, start_t = False, None, d.get("time", 0)
            elif kind == "ready":
                ready = True
            elif kind == "error":
                error = val
    except Exception:
        pass
    return ready, error, start_t


def is_alive(url):
    try:
        r = requests.get(url, timeout=10, allow_redirects=True)
        return r.status_code == 200
    except Exception:
        return False


def kernel_busy(api):
    try:
        res = api.kernels_status(f"{KAGGLE_USERNAME}/{SLUG}")
        s = str(getattr(res, "status", res)).lower()
        return "running" in s or "queued" in s
    except Exception:
        return False


def push_kernel(api):
    code = (KAGGLE_SCRIPT
            .replace("__TOPIC__", TOPIC)
            .replace("__CFTOKEN__", CF_TOKEN)
            .replace("__URL__", DOMAIN_URL))
    folder = tempfile.mkdtemp()
    with open(os.path.join(folder, "script.py"), "w", encoding="utf-8") as f:
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
    with open(os.path.join(folder, "kernel-metadata.json"), "w") as f:
        json.dump(meta, f)
    api.kernels_push(folder)


def show_link():
    st.link_button("🔗 ဖွင့်မယ်", DOMAIN_URL, use_container_width=True)
    st.code(DOMAIN_URL, language=None)


def run(force):
    if not KAGGLE_KEY or not CF_TOKEN:
        st.error("Secrets ထဲမှာ KAGGLE_KEY နဲ့ CF_TUNNEL_TOKEN ထည့်ပါ။")
        return

    with st.status("စစ်ဆေးနေတယ်...", expanded=False) as s:
        if not force and is_alive(DOMAIN_URL):
            s.update(label="အဆင်သင့်ဖြစ်ပြီ", state="complete")
            show_link()
            return

        try:
            api = KaggleApi()
            api.authenticate()
        except Exception as e:
            s.update(label="Kaggle login မရပါ", state="error")
            st.error(str(e))
            return

        pushed, t_push = False, 0
        if not force and kernel_busy(api):
            s.update(label="Kaggle စတင်နေတုန်း... စောင့်နေတယ်")
        else:
            try:
                push_kernel(api)
            except Exception as e:
                s.update(label="Push မအောင်မြင်ပါ", state="error")
                st.error(str(e))
                return
            pushed, t_push = True, time.time()
            s.update(label="Kaggle စတင်နေတယ်...")

        fresh_after = (t_push - 10) if pushed else 0
        ok = False

        for _ in range(300):
            ready, error, start_t = read_state()
            fresh = start_t > 0 and start_t >= fresh_after

            if fresh and error:
                s.update(label="Error ဖြစ်သွားတယ်", state="error")
                st.error(error)
                return

            if fresh and ready:
                ok = True
                break
            time.sleep(2)

        if not ok:
            s.update(label="အချိန်ကုန်သွားတယ်", state="error")
            st.warning("Kaggle → Your Work → Logs ကို စစ်ပါ။")
            return

        s.update(label="Domain စစ်နေတယ်...")
        for _ in range(20):
            if is_alive(DOMAIN_URL):
                break
            time.sleep(3)

        s.update(label="အဆင်သင့်ဖြစ်ပြီ", state="complete")

    show_link()


# ==========================================
# UI
# ==========================================
st.title("🔗 Kaggle Runner")

c1, c2 = st.columns(2)
with c1:
    start = st.button("🚀 စတင်မယ်", use_container_width=True, type="primary")
with c2:
    restart = st.button("🔄 ပြန်စမယ်", use_container_width=True)

if start:
    run(False)
elif restart:
    run(True)
