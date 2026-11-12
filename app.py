import os, json, time, tempfile
import requests
import streamlit as st

# ==========================================
# Settings
# ==========================================
KAGGLE_USERNAME = "thetuaiaa"
KAGGLE_KEY = "KGAT_31605077f91a8c94985138dcae838c69"

SLUG = "my-link-runner"
GPU_ENABLED = False
TOPIC = "kgl-k-7f3a9c2e51b84d06"

os.environ["KAGGLE_USERNAME"] = KAGGLE_USERNAME
os.environ["KAGGLE_KEY"] = KAGGLE_KEY
os.environ["KAGGLE_API_TOKEN"] = KAGGLE_KEY

st.set_page_config(page_title="Gradio Link", page_icon="🔗", layout="centered")

st.markdown(
    """
    <style>
    #MainMenu, footer, header {visibility: hidden;}
    .block-container {padding-top: 3rem; max-width: 520px;}
    .hero {text-align: center; margin-bottom: 1.5rem;}
    .hero h1 {font-size: 1.7rem; margin: 0;}
    .hero p {opacity: .65; margin: .3rem 0 0; font-size: .95rem;}
    .stButton > button, .stLinkButton > a {
        width: 100%; border-radius: 12px; padding: .7rem 1rem; font-weight: 600;
    }
    </style>
    <div class="hero">
        <h1>🔗 Gradio Link</h1>
        <p>Kaggle ကနေ share link ထုတ်ပေးမယ်</p>
    </div>
    """,
    unsafe_allow_html=True,
)

from kaggle.api.kaggle_api_extended import KaggleApi

# ==========================================
# Kaggle မှာ Run မယ့် Script (Gradio link တစ်ခုတည်း)
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
T0 = time.time()

def say(msg):
    print(f"[{time.time() - T0:5.1f}s] {msg}", flush=True)

def sh(cmd):
    p = subprocess.run(cmd, shell=True, text=True, capture_output=True)
    return p.returncode, (p.stdout + p.stderr)

def tail_log(n=3000):
    try:
        with open(LOG, encoding="utf-8", errors="ignore") as f:
            return f.read()[-n:]
    except Exception:
        return "(log မရှိသေးပါ)"

def post(kind, text):
    try:
        requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=f"{kind}|{text}".encode("utf-8"),
            timeout=15,
        )
    except Exception as e:
        print("ntfy error:", e)

post("start", str(time.time()))
sh("pkill -f '[p]ython.*app.py'")
time.sleep(0.3)

# ---------------------------------------------------------- App ပြင်ဆင်ခြင်း
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
            "huggingface_hub": "huggingface_hub",
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
    need = [
        "ffmpeg", "libraqm0", "libfribidi0",
        "fonts-noto-core", "fonts-noto-cjk",
        "fonts-dejavu-core", "fonts-sil-padauk",
    ]
    missing = [p for p in need if sh(f"dpkg -s {p}")[0] != 0]
    if missing:
        say(f"apt install: {', '.join(missing)}")
        cmd = (
            "DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "
            f"--no-install-recommends {' '.join(missing)}"
        )
        rc, _ = sh(cmd)
        if rc != 0:
            sh("apt-get update -qq")
            sh(cmd)
    RES["apt"] = True
    say("apt ✅ (ffmpeg / fonts ပြီး)")

t_git = threading.Thread(target=task_git)
t_pip = threading.Thread(target=task_pip)
t_apt = threading.Thread(target=task_apt)
for t in (t_git, t_pip, t_apt):
    t.start()

t_git.join()
t_pip.join()
if RES.get("git", (1,))[0] != 0:
    post("error", "git clone/update မအောင်မြင်ပါ: " + RES["git"][1][-300:])
    raise SystemExit("git မအောင်မြင်ပါ")

os.chdir(REPO_DIR)

# ---------------------------------------------------------- Nara Mini offline Burmese TTS
# Download only the ONNX/frontend files needed for local CPU inference.
NARA_DIR = "/kaggle/working/nara-mini-v1"
try:
    from huggingface_hub import snapshot_download
    if not os.path.isfile(os.path.join(NARA_DIR, "synthesize.py")):
        say("Nara model download စနေတယ်...")
        snapshot_download(
            repo_id="YeeNyunn/nara-mini-v1",
            local_dir=NARA_DIR,
            allow_patterns=[
                "synthesize.py", "requirements.txt", "config.json",
                "inference_config.json", "frontend/*", "onnx/*/*",
            ],
        )
    rc, out = sh(f"{sys.executable} -m pip install -q -r {NARA_DIR}/requirements.txt")
    if rc != 0:
        raise RuntimeError(out[-800:])
    os.environ["NARA_MODEL_DIR"] = NARA_DIR
    os.environ.setdefault("NARA_THREADS", "2")
    say("Nara offline TTS ✅")
except Exception as ex:
    say(f"Nara offline TTS ⚠️ မတင်နိုင်သေးပါ: {str(ex)[-500:]}")

if not os.path.exists(APP_FILE):
    post("error", "app.py repo ထဲမှာ မရှိပါ")
    raise SystemExit("app.py မရှိပါ")

fonts = [f for f in os.listdir(".") if f.lower().endswith((".ttf", ".otf", ".ttc"))]
if fonts:
    os.environ["RECAP_FONT"] = os.path.abspath(
        "MyanmarPadaung.ttf" if "MyanmarPadaung.ttf" in fonts else sorted(fonts)[0]
    )
os.environ["GRADIO_ANALYTICS_ENABLED"] = "False"

# Gradio launch ကို share=True ဖြစ်အောင် patch လုပ်တဲ့ wrapper
WRAPPER = """
import runpy, gradio, sys

_original_launch = gradio.Blocks.launch
def _patched_launch(self, *args, **kwargs):
    kwargs['share'] = True
    kwargs['server_name'] = '0.0.0.0'
    return _original_launch(self, *args, **kwargs)
gradio.Blocks.launch = _patched_launch

sys.argv = ["app.py"]
runpy.run_path("app.py", run_name="__main__")
"""
with open("_gradio_share_wrapper.py", "w") as f:
    f.write(WRAPPER)

env = dict(os.environ, PORT=str(PORT))
app_proc = subprocess.Popen(
    [sys.executable, "-u", "_gradio_share_wrapper.py"],
    stdout=open(LOG, "w"),
    stderr=subprocess.STDOUT,
    env=env,
)
say("app စတင်နေတယ် (Gradio Share)...")

# Link ပေါ်တာနဲ့ ချက်ချင်းပို့မယ်
GRADIO_LINK_PATTERN = re.compile(r"https://[a-zA-Z0-9\-]+\.gradio\.live")
ready = False

for _ in range(1200):
    if app_proc.poll() is not None:
        print(f"❌ App crash (exit {app_proc.returncode})")
        print(tail_log())
        post("error", "App crash: " + tail_log(400))
        break

    m = GRADIO_LINK_PATTERN.search(tail_log(5000))
    if m:
        link = m.group(0)
        say(f"gradio_share ✅ {link}")
        post("link", f"gradio={link}")
        post("ready", "1")
        ready = True
        break

    time.sleep(0.3)

if not ready:
    print("⚠️ Gradio link မထွက်ပါ — log:\n")
    print(tail_log())
    post("error", "Gradio link မထွက်ပါ: " + tail_log(400))
    raise SystemExit("Link မထွက်လို့ ရပ်လိုက်တယ်။")

print(f"Running... log: {LOG}")
while True:
    time.sleep(30)
    if app_proc.poll() is not None:
        print(f"❌ App ရပ်သွားပြီ (exit {app_proc.returncode}) — log:\n")
        print(tail_log())
        break
'''

# Kaggle credentials
if not KAGGLE_USERNAME or not KAGGLE_KEY:
    st.error("KAGGLE_USERNAME / KAGGLE_KEY မတွေ့ပါ။")
    st.stop()

# ==========================================
# Helpers
# ==========================================
def read_state():
    links, ready, error, start_t = {}, False, None, 0
    try:
        r = requests.get(
            f"https://ntfy.sh/{TOPIC}/json?poll=1&since=all",
            timeout=10,
        )
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
                try:
                    start_t = float(val)
                except Exception:
                    start_t = d.get("time", 0)
                links, ready, error = {}, False, None
            elif kind == "link" and "=" in val:
                name, url = val.split("=", 1)
                if name == "gradio":
                    links["gradio"] = url
            elif kind == "cloudflare":
                links["gradio"] = val
            elif kind == "ready":
                ready = True
            elif kind == "error":
                error = val
    except Exception:
        pass
    return links, ready, error, start_t


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
        return ("running" in s) or ("queued" in s)
    except Exception as e:
        print("kernel_busy error:", e)
        return False


def push_kernel(api):
    code = KAGGLE_SCRIPT.replace("__TOPIC__", TOPIC)
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


def fetch_link(force):
    """Link ရရင် url ပြန်ပေးမယ်၊ မရရင် None။ Progress ကို st.status ထဲမှာပြမယ်။"""
    with st.status("ပြင်ဆင်နေတယ်...", expanded=False) as status:
        api = KaggleApi()
        api.authenticate()

        if not force:
            links, _, _, _ = read_state()
            for v in links.values():
                if is_alive(v):
                    status.update(label="ရပြီ", state="complete")
                    return v

        pushed, t_push = False, 0
        if not force and kernel_busy(api):
            status.update(label="Kaggle စတင်နေတုန်း — စောင့်နေတယ်...")
        else:
            try:
                push_kernel(api)
            except Exception as e:
                status.update(label="Push မအောင်မြင်ပါ", state="error")
                st.error(str(e))
                return None
            pushed, t_push = True, time.time()
            status.update(label="Kaggle စတင်နေတယ်...")

        fresh_after = (t_push - 10) if pushed else 0

        for _ in range(600):
            links, ready, error, start_t = read_state()
            fresh = start_t > 0 and start_t >= fresh_after

            if fresh and error:
                status.update(label="Error ဖြစ်သွားတယ်", state="error")
                st.error(error)
                return None

            if fresh and links:
                status.update(label="ရပြီ", state="complete")
                return list(links.values())[0]

            time.sleep(1)

        status.update(label="အချိန်ကုန်သွားပြီ", state="error")
        st.warning("Kaggle → Your Work → Logs ကို စစ်ကြည့်ပါ။")
        return None


# ==========================================
# UI
# ==========================================
link = st.session_state.get("link")

if not link:
    if st.button("Link ယူမယ်", type="primary"):
        url = fetch_link(force=False)
        if url:
            st.session_state["link"] = url
            st.rerun()
else:
    st.success("အဆင်သင့်ဖြစ်ပါပြီ")
    st.code(link, language=None)
    st.link_button("ဖွင့်မယ်", link, type="primary")
    if st.button("အသစ်ထုတ်မယ်"):
        st.session_state["link"] = None
        url = fetch_link(force=True)
        if url:
            st.session_state["link"] = url
        st.rerun()