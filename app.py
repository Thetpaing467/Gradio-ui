import os, json, time, tempfile
import requests
import streamlit as st

# ==========================================
# ⚙️ Settings  (key ကို Streamlit secrets ထဲထည့်ပါ)
# .streamlit/secrets.toml  သို့မဟုတ် Streamlit Cloud > Secrets
#   KAGGLE_USERNAME = "thetuaiaa"
#   KAGGLE_KEY = "NEW_KEY_HERE"
#   NGROK_TOKEN = "..."
#   NGROK_DOMAIN = "whisking-unvarying-citadel.ngrok-free.dev"
# ==========================================
KAGGLE_USERNAME = st.secrets.get("KAGGLE_USERNAME", os.environ.get("KAGGLE_USERNAME", "thetuaiaa"))
KAGGLE_KEY = st.secrets.get("KAGGLE_KEY", os.environ.get("KAGGLE_KEY", ""))

# 🔗 ngrok ပုံသေ Domain  (ngrok dashboard > Domains ထဲက free domain ကို ဒီမှာထည့်ပါ)
NGROK_TOKEN = st.secrets.get("NGROK_TOKEN", os.environ.get(
    "NGROK_TOKEN", "3Jh9mozyHp150UpQiuvuPpZDZ36_7U2RiuikZjquzgVN9nVNp"))
NGROK_DOMAIN = st.secrets.get("NGROK_DOMAIN", os.environ.get(
    "NGROK_DOMAIN", "whisking-unvarying-citadel.ngrok-free.dev"))

SLUG = "my-link-runner"
GPU_ENABLED = False
TOPIC = "kgl-k-7f3a9c2e51b84d06"

os.environ["KAGGLE_USERNAME"] = KAGGLE_USERNAME
os.environ["KAGGLE_KEY"] = KAGGLE_KEY
from kaggle.api.kaggle_api_extended import KaggleApi

st.set_page_config(page_title="Kaggle Gradio Link", page_icon="🔗")
st.title("🔗 Kaggle Gradio Link ထုတ်စက် (ပုံသေ Domain)")

# ==========================================
# Kaggle မှာ Run မယ့် Script
# ==========================================
KAGGLE_SCRIPT = r'''
import os, re, sys, time, socket, subprocess, threading
from importlib import metadata
import requests

NTFY_TOPIC = "__TOPIC__"
NGROK_TOKEN = "__NGROK_TOKEN__"
NGROK_DOMAIN = "__NGROK_DOMAIN__"
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
        return open(LOG, encoding="utf-8", errors="ignore").read()[-n:]
    except Exception:
        return "(log မရှိသေးပါ)"

def post(kind, text):
    try:
        requests.post(f"https://ntfy.sh/{NTFY_TOPIC}",
                      data=f"{kind}|{text}".encode("utf-8"), timeout=15)
    except Exception as e:
        print("ntfy error:", e)

post("start", "1")
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
        "pyngrok": "pyngrok",
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
if not os.path.exists(APP_FILE):
    post("error", "app.py repo ထဲမှာ မရှိပါ")
    raise SystemExit("app.py မရှိပါ")

fonts = [f for f in os.listdir(".") if f.lower().endswith((".ttf", ".otf", ".ttc"))]
if fonts:
    os.environ["RECAP_FONT"] = os.path.abspath(
        "MyanmarPadaung.ttf" if "MyanmarPadaung.ttf" in fonts else sorted(fonts)[0])
os.environ["GRADIO_ANALYTICS_ENABLED"] = "False"

# Gradio ကို share မသုံးဘဲ port ပုံသေနဲ့ run ခိုင်းတဲ့ wrapper (ngrok က ပုံသေ domain ပေးမယ်)
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
say("app စတင်နေတယ် (ngrok ပုံသေ domain)...")

# App port ဖွင့်ပြီဆိုတာနဲ့ ngrok tunnel ဖွင့်ပြီး link ပို့မယ်
from pyngrok import ngrok, conf
ngrok.install_ngrok()
NGROK_BIN = conf.get_default().ngrok_path
NGROK_LOG = "/kaggle/working/ngrok.log"

def ngrok_tail(n=600):
    try:
        return open(NGROK_LOG, encoding="utf-8", errors="ignore").read()[-n:]
    except Exception:
        return "(ngrok log မရှိ)"

ready = False
ngrok_proc = None
for _ in range(1200):
    if app_proc.poll() is not None:
        print(f"❌ App crash (exit {app_proc.returncode})")
        print(tail_log())
        post("error", "App crash: " + tail_log(400))
        break

    try:
        socket.create_connection(("127.0.0.1", PORT), timeout=1).close()
    except OSError:
        time.sleep(0.3)
        continue

    # ngrok agent ကို တိုက်ရိုက် run (pyngrok API အဟောင်း မသုံးတော့ဘူး)
    ngrok_proc = subprocess.Popen(
        [NGROK_BIN, "http", str(PORT), f"--url=https://{NGROK_DOMAIN}",
         f"--authtoken={NGROK_TOKEN}", "--log=stdout"],
        stdout=open(NGROK_LOG, "w"), stderr=subprocess.STDOUT)

    up = False
    for _ in range(80):
        time.sleep(0.5)
        if ngrok_proc.poll() is not None:
            break
        try:
            r = requests.get("http://127.0.0.1:4040/api/tunnels", timeout=2)
            if r.json().get("tunnels"):
                up = True
                break
        except Exception:
            pass

    if up:
        link = f"https://{NGROK_DOMAIN}"
        say(f"ngrok ✅ {link}")
        post("cloudflare", link)
        post("ready", "1")
        ready = True
    else:
        err = ngrok_tail()
        print("ngrok error:", err)
        post("error", "ngrok error: " + err[-350:])
    break

if not ready:
    print("⚠️ Link မထွက်ပါ — log:\n")
    print(tail_log())
    raise SystemExit("Link မထွက်လို့ ရပ်လိုက်တယ်။")

print(f"Running... log: {LOG}")
while True:
    time.sleep(30)
    if app_proc.poll() is not None:
        print(f"❌ App ရပ်သွားပြီ (exit {app_proc.returncode}) — log:\n")
        print(tail_log())
        break
'''

# ==========================================
# Helpers
# ==========================================
def read_state():
    links, ready, error, start_t = {}, False, None, 0
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
                links, ready, error, start_t = {}, False, None, d.get("time", 0)
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
        r = requests.get(url, timeout=10, allow_redirects=True,
                         headers={"ngrok-skip-browser-warning": "1"})
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
            .replace("__NGROK_TOKEN__", NGROK_TOKEN)
            .replace("__NGROK_DOMAIN__", NGROK_DOMAIN))
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

def show_link(status, box, v):
    status.success("✅ Link အဆင်သင့်ဖြစ်ပါပြီ!")
    box.empty()
    st.markdown(f"### 🔗 [{v}]({v})")
    st.code(v)

FIXED_URL = f"https://{NGROK_DOMAIN}"

def run(force):
    status, box = st.empty(), st.empty()
    api = KaggleApi()
    api.authenticate()

    # Link ပုံသေမို့ အသက်ရှိနေရင် ချက်ချင်းပြ
    if not force and is_alive(FIXED_URL):
        show_link(status, box, FIXED_URL)
        return

    pushed, t_push = False, 0
    if not force and kernel_busy(api):
        status.info("⏳ Kaggle session run/စတင်နေတုန်းပါ — စောင့်နေတယ်...")
    else:
        try:
            push_kernel(api)
        except Exception as e:
            status.error(f"Push မအောင်မြင်ပါ: {e}")
            return
        pushed, t_push = True, time.time()
        status.info("⏳ Kaggle စတင်နေတယ်... (၁ မိနစ်ဝန်းကျင် ကြာနိုင်တယ်)")

    fresh_after = (t_push - 10) if pushed else 0

    for i in range(600):
        # ntfy ကို ၅ စက္ကန့်တစ်ခါပဲ စစ် (error သိဖို့သာ)
        if i % 5 == 0:
            _, _, error, start_t = read_state()
            if error and start_t > 0 and start_t >= fresh_after:
                status.error(f"❌ Kaggle မှာ error: {error}")
                return

        if is_alive(FIXED_URL):
            show_link(status, box, FIXED_URL)
            return

        time.sleep(1)

    status.warning("မအောင်မြင်သေးပါ။ Kaggle → Your Work → Logs ကို စစ်ကြည့်ပါ။")

# ==========================================
# Streamlit UI
# ==========================================
st.info(f"🚀 ဒီစနစ်က ngrok **ပုံသေ Domain** (`{NGROK_DOMAIN}`) နဲ့ Gradio app ကို ဖွင့်ပေးမှာပါ။")

if st.button("🚀 Link ယူမယ်"):
    run(False)

if st.button("🔄 အသစ်အတင်းထုတ်မယ်"):
    run(True)
