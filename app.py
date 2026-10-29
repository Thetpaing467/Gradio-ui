import os, json, time, tempfile
import requests
import streamlit as st

# ==========================================
# ⚙️ ခင်ဗျားရဲ့ Kaggle အချက်အလက်တွေ
# ==========================================
KAGGLE_USERNAME = "thetuaiaa"
KAGGLE_KEY = "e949c9ede1ed6d03eda8811b5421a262"
SLUG = "my-link-runner"
GPU_ENABLED = False   # CPU သက်သက်
TOPIC = "kgl-k-7f3a9c2e51b84d06" 

os.environ["KAGGLE_USERNAME"] = KAGGLE_USERNAME
os.environ["KAGGLE_KEY"] = KAGGLE_KEY
from kaggle.api.kaggle_api_extended import KaggleApi

st.set_page_config(page_title="Kaggle Link ထုတ်စက် (CPU)", page_icon="🔗")
st.title("🔗 Kaggle Link ထုတ်စက် (CPU မြန်မြန်)")
st.markdown("---")

# ==========================================
# Kaggle မှာ Run မယ့် Script (Gradio Share ကို အတင်း ထုတ်ခိုင်းထားတယ်)
# ==========================================
KAGGLE_SCRIPT = r'''
import os, re, sys, time, subprocess, threading, urllib.request
from importlib import metadata
import requests

NTFY_TOPIC = "__TOPIC__"
REPO_URL = "https://github.com/Thetpaing467/new.git"
REPO_DIR = "/kaggle/working/new"
APP_FILE = "app.py"
PORT = 7860
LOG = "/kaggle/working/app.log"
CF = "/kaggle/working/cloudflared"
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
sh("pkill -f 'cloudflared tunnel' ; pkill -f 'python.*app.py'")
time.sleep(1)

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
    say("apt ✅ (ffmpeg / fonts ပြီး)")

def task_cf():
    if not os.path.exists(CF):
        sh(f"wget -q -O {CF} https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 && chmod +x {CF}")
    RES["cf"] = os.path.exists(CF)
    say("cloudflared ✅" if RES["cf"] else "cloudflared ❌")

url_ready = threading.Event()
tunnel_url = {}

def task_tunnel():
    t_cf.join()
    if not RES.get("cf"):
        return
    tun = subprocess.Popen([CF, "tunnel", "--url", f"http://localhost:{PORT}", "--no-autoupdate"],
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    RES["tun"] = tun
    for line in tun.stdout:
        m = re.search(r"https://[a-z0-9\-]+\.trycloudflare\.com", line)
        if m and not url_ready.is_set():
            tunnel_url["u"] = m.group(0)
            url_ready.set()
            say("tunnel ✅")
            post("cloudflare", m.group(0))

t_git = threading.Thread(target=task_git)
t_pip = threading.Thread(target=task_pip)
t_apt = threading.Thread(target=task_apt)
t_cf = threading.Thread(target=task_cf)
t_tun = threading.Thread(target=task_tunnel, daemon=True)
for t in (t_git, t_pip, t_apt, t_cf, t_tun):
    t.start()

t_git.join()
t_pip.join()
if RES.get("git", (1,))[0] != 0:
    post("error", "git မအောင်မြင်ပါ")
    raise SystemExit("git error")

os.chdir(REPO_DIR)
if not os.path.exists(APP_FILE):
    post("error", "app.py မရှိပါ")
    raise SystemExit("app.py error")

fonts = [f for f in os.listdir(".") if f.lower().endswith((".ttf", ".otf", ".ttc"))]
if fonts:
    os.environ["RECAP_FONT"] = os.path.abspath("MyanmarPadaung.ttf" if "MyanmarPadaung.ttf" in fonts else sorted(fonts)[0])
os.environ["GRADIO_ANALYTICS_ENABLED"] = "False"

# ⭐⭐⭐ Gradio ကို Share Link အတင်း ထုတ်ခိုင်းမယ့် Wrapper (အဆင့်မြှင့်ထားတယ်) ⭐⭐⭐
WRAPPER_CODE = """
import runpy, gradio, sys, os

# Gradio ရဲ့ Share Server ကို တိုက်ရိုက် သတ်မှတ်ပေးမယ် (Error တက်တာ သက်သာသွားမယ်)
os.environ["GRADIO_SHARE_SERVER_ADDRESS"] = "https://share.gradio.live" 
os.environ["GRADIO_SHARE_SERVER_PORT"] = "443"

_original_launch = gradio.Blocks.launch
def _patched_launch(self, *args, **kwargs):
    kwargs['share'] = True
    kwargs['server_name'] = '0.0.0.0'
    kwargs['share_server_address'] = 'share.gradio.live:443'
    kwargs['share_server_protocol'] = 'https'
    kwargs['max_threads'] = 40 # Thread တွေ ပိုတိုးပေးမယ်
    return _original_launch(self, *args, **kwargs)

gradio.Blocks.launch = _patched_launch
sys.argv = ["app.py"]
runpy.run_path("app.py", run_name="__main__")
"""
with open("_share_wrapper.py", "w") as f:
    f.write(WRAPPER_CODE)

env = dict(os.environ, PORT=str(PORT))
app_proc = subprocess.Popen([sys.executable, "-u", "_share_wrapper.py"],
                            stdout=open(LOG, "w"), stderr=subprocess.STDOUT, env=env)
say("app စတင်နေတယ်...")

started = False
gradio_link = None
GRADIO_LINK_PATTERN = re.compile(r"https://[a-zA-Z0-9\-]+\.gradio\.live")

for _ in range(360):
    if app_proc.poll() is not None:
        post("error", "App crash: " + tail_log(400))
        break
    if not gradio_link:
        log_data = tail_log(5000)
        m = GRADIO_LINK_PATTERN.search(log_data)
        if m:
            gradio_link = m.group(0)
            say(f"Gradio Link ✅ {gradio_link}")
            post("gradio", gradio_link)
    if not started:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}", timeout=1)
            started = True
            say("app ✅")
            post("ready", "1")
            break
        except Exception:
            pass
    time.sleep(0.5)

if not started:
    post("error", "App မတက်ပါ")
    raise SystemExit("App မတက်")

print(f"Running... log: {LOG}")
while True:
    time.sleep(30)
    if app_proc.poll() is not None:
        post("error", "App ရပ်သွားပြီ")
        break
'''

# ==========================================
# Streamlit Helpers
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
            elif kind in ["gradio", "cloudflare"]:
                links[kind] = val
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
        return "running" in s or "queued" in s
    except Exception:
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
        "enable_gpu": "false", # CPU
        "enable_internet": "true",
    }
    with open(os.path.join(folder, "kernel-metadata.json"), "w") as f:
        json.dump(meta, f)
    api.kernels_push(folder)

def show_final(links):
    st.markdown("### 🔗 ဖွင့်လို့ရတဲ့ Link တွေ")
    
    if "gradio" in links:
        st.success("⭐ **Gradio Share Link** (ဖုန်းကနေ ဝင်ရင် ဒါကို သုံးပါ - Error ကင်း၊ VPN မခံ)")
        st.code(links["gradio"])
        st.markdown(f"[🔗 ဒီနေရာကို နှိပ်ပြီး ဖွင့်ပါ]({links['gradio']})")
    
    if "cloudflare" in links:
        st.info("🌐 **Cloudflare Link** (အရန်)")
        st.code(links["cloudflare"])
        st.markdown(f"[🔗 ဒီနေရာကို နှိပ်ပြီး ဖွင့်ပါ]({links['cloudflare']})")

def run(force):
    status, box = st.empty(), st.empty()
    api = KaggleApi()
    api.authenticate()

    if not force:
        links, _, _, _ = read_state()
        alive = {k: v for k, v in links.items() if is_alive(v)}
        if alive:
            status.success("♻️ အရင် Link သုံးလို့ရသေးတယ် — အသစ်မထုတ်ပါ")
            show_final(alive)
            return

    pushed, t_push = False, 0
    if not force and kernel_busy(api):
        status.info("⏳ Kaggle session run/စတင်နေတုန်းပါ — Link စောင့်နေတယ်...")
    else:
        try:
            push_kernel(api)
        except Exception as e:
            status.error(f"Push မအောင်မြင်ပါ: {e}")
            return
        pushed, t_push = True, time.time()
        status.info("⏳ Kaggle (CPU) စတင်နေတယ်... (Link ထုတ်နေတယ်)")

    fresh_after = (t_push - 10) if pushed else 0

    for _ in range(300):
        links, ready, error, start_t = read_state()
        fresh = start_t > 0 and start_t >= fresh_after
        
        if fresh and links:
            box.markdown(f"**ရရှိထားတဲ့ Link:** `{list(links.values())[0]}`")
            if not ready:
                status.info("⏳ Link ရပါပြီ၊ App စတက်နေတယ်... ခဏနေမှ ဖွင့်ပါ")
                
        if fresh and error:
            status.error(f"❌ Kaggle မှာ error: {error}")
            return
            
        if fresh and ready and links:
            alive = {k: v for k, v in links.items() if is_alive(v)}
            if alive:
                status.success("✅ Link တွေ အဆင်သင့်ဖြစ်ပါပြီ!")
                box.empty()
                show_final(alive)
                return
        time.sleep(2)

    status.warning("မအောင်မြင်သေးပါ။ Kaggle → Your Work → Logs ကို စစ်ကြည့်ပါ။")

# ==========================================
# Streamlit UI 
# ==========================================
with st.sidebar:
    st.header("⚙️ လမ်းညွှန်")
    st.markdown("""
    - **CPU သက်သက်** ဖြစ်လို့ မြန်ပါတယ်။
    - **Link ယူမယ်** ကို နှိပ်ပြီး ၁-၃ မိနစ် စောင့်ပါ။
    - ရလာတဲ့ **⭐ Gradio Link** ကို ဖုန်းကနေ ဖွင့်ပါ။
    """)

st.info("💡 ဒီစနစ်က CPU ကို သုံးထားလို့ မြန်မြန် Link ထွက်ပါလိမ့်မယ်။")

col1, col2 = st.columns(2)
with col1:
    if st.button("🚀 Link ယူမယ်", use_container_width=True):
        run(False)
with col2:
    if st.button("🔄 အသစ်အတင်းထုတ်မယ်", use_container_width=True):
        run(True)