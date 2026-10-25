import os, json, time, tempfile, hashlib
import requests
import streamlit as st

KAGGLE_USERNAME = "thetuaiaa"
KAGGLE_KEY = "e949c9ede1ed6d03eda8811b5421a262"

os.environ["KAGGLE_USERNAME"] = KAGGLE_USERNAME
os.environ["KAGGLE_KEY"] = KAGGLE_KEY
from kaggle.api.kaggle_api_extended import KaggleApi

# link မှတ်ထားမယ့် ntfy topic (အမြဲတူတယ်၊ ခန့်မှန်းလို့မရအောင် key hash သုံးထား)
STATE_TOPIC = "kgl-" + hashlib.sha256(KAGGLE_KEY.encode()).hexdigest()[:16]
NAMES = {"pinggy": "Pinggy", "cloudflare": "Cloudflare", "ngrok": "ngrok"}

st.set_page_config(page_title="Kaggle Link ထုတ်စက်", page_icon="🔗")
st.title("🔗 Kaggle Public Link ထုတ်စက်")

KAGGLE_SCRIPT = r'''
import os, re, sys, time, subprocess, threading, urllib.request
from importlib import metadata
import requests

NTFY_TOPIC = "__TOPIC__"
NGROK_TOKEN = "__NGROK__"
REPO_URL = "https://github.com/Thetpaing467/new.git"
REPO_DIR = "/kaggle/working/new"
APP_FILE = "app.py"
PORT = 7860
LOG = "/kaggle/working/app.log"
CF = "/kaggle/working/cloudflared"
T0 = time.time()
ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


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


post("start", "1")  # run အသစ်စပြီ (အရင် link တွေကို မမှန်တော့ဘူးလို့ သတ်မှတ်)

sh("pkill -f '[c]loudflared tunnel' ; pkill -f '[p]ython.*app.py'")
time.sleep(1)


def run_pinggy():
    if sh("which ssh")[0] != 0:
        sh("apt-get update -qq && apt-get install -y -qq openssh-client")
    p = subprocess.Popen(
        ["ssh", "-p", "443",
         "-o", "StrictHostKeyChecking=no",
         "-o", "UserKnownHostsFile=/dev/null",
         "-o", "ServerAliveInterval=30",
         f"-R0:localhost:{PORT}", "a.pinggy.io"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True)
    sent = False
    for line in p.stdout:
        line = ANSI.sub("", line)
        m = re.search(r"https://[a-zA-Z0-9\-\.]+pinggy\.(?:link|io|online)", line)
        if m and not sent:
            sent = True
            say("pinggy ✅")
            post("pinggy", m.group(0))


def run_cloudflared():
    if not os.path.exists(CF):
        sh(f"wget -q -O {CF} https://github.com/cloudflare/cloudflared/releases/latest/"
           f"download/cloudflared-linux-amd64 && chmod +x {CF}")
    if not os.path.exists(CF):
        say("cloudflared ❌")
        return
    p = subprocess.Popen(
        [CF, "tunnel", "--url", f"http://localhost:{PORT}", "--no-autoupdate"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    sent = False
    for line in p.stdout:
        m = re.search(r"https://[a-z0-9\-]+\.trycloudflare\.com", line)
        if m and not sent:
            sent = True
            say("cloudflare ✅")
            post("cloudflare", m.group(0))


def run_ngrok():
    if not NGROK_TOKEN:
        return
    try:
        sh(f"{sys.executable} -m pip install -q pyngrok")
        from pyngrok import ngrok
        ngrok.set_auth_token(NGROK_TOKEN)
        t = ngrok.connect(PORT, "http")
        say("ngrok ✅")
        post("ngrok", t.public_url.replace("http://", "https://"))
    except Exception as e:
        say(f"ngrok ❌ {e}")


for fn in (run_pinggy, run_cloudflared, run_ngrok):
    threading.Thread(target=fn, daemon=True).start()

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
print("Repo files:", sorted(os.listdir(".")))
if not os.path.exists(APP_FILE):
    post("error", "app.py repo ထဲမှာ မရှိပါ")
    raise SystemExit("app.py မရှိပါ")

fonts = [f for f in os.listdir(".") if f.lower().endswith((".ttf", ".otf", ".ttc"))]
if fonts:
    os.environ["RECAP_FONT"] = os.path.abspath(
        "MyanmarPadaung.ttf" if "MyanmarPadaung.ttf" in fonts else sorted(fonts)[0])
    print("Font:", os.environ["RECAP_FONT"])
os.environ["GRADIO_ANALYTICS_ENABLED"] = "False"

env = dict(os.environ, PORT=str(PORT))
app_proc = subprocess.Popen([sys.executable, "-u", APP_FILE],
                            stdout=open(LOG, "w"), stderr=subprocess.STDOUT, env=env)
say("app စတင်နေတယ်...")

started = False
for _ in range(360):
    if app_proc.poll() is not None:
        print(f"❌ App crash (exit {app_proc.returncode}) — log:\n")
        print(tail_log())
        post("error", "App crash: " + tail_log(400))
        break
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{PORT}", timeout=1)
        started = True
        say("app ✅")
        post("ready", "1")
        break
    except Exception:
        time.sleep(0.5)
else:
    print("⚠️ App မတက်သေးဘူး — log:\n")
    print(tail_log())
    post("error", "App မတက်ပါ: " + tail_log(400))

if not started:
    raise SystemExit("App မတက်လို့ ရပ်လိုက်တယ်။")

print(f"Running... log: {LOG}")
while True:
    time.sleep(30)
    if app_proc.poll() is not None:
        print(f"❌ App ရပ်သွားပြီ (exit {app_proc.returncode}) — log:\n")
        print(tail_log())
        break
'''


# ------------------------------------------------------------ helper functions
def read_state():
    """ntfy ထဲက နောက်ဆုံး run ရဲ့ အခြေအနေကို ဖတ်မယ်"""
    links, ready, error, start_t = {}, False, None, 0
    try:
        r = requests.get(
            f"https://ntfy.sh/{STATE_TOPIC}/json?poll=1&since=all", timeout=10
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
                links, ready, error, start_t = {}, False, None, d.get("time", 0)
            elif kind in NAMES:
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
        r = requests.get(url, timeout=6, headers={"ngrok-skip-browser-warning": "1"})
        return r.status_code == 200
    except Exception:
        return False


def kernel_busy(api, slug):
    try:
        res = api.kernels_status(f"{KAGGLE_USERNAME}/{slug}")
        s = str(getattr(res, "status", res)).lower()
        return "running" in s or "queued" in s
    except Exception:
        return False


def links_md(links):
    return "\n\n".join(f"🔗 **{NAMES[k]}:** [{v}]({v})" for k, v in links.items())


def show_final(links):
    st.markdown(links_md(links))
    for k, v in links.items():
        st.caption(NAMES[k])
        st.code(v)


def push_kernel(api, slug, gpu, ngrok_token):
    code = (KAGGLE_SCRIPT.replace("__TOPIC__", STATE_TOPIC)
                         .replace("__NGROK__", ngrok_token.strip()))
    folder = tempfile.mkdtemp()
    with open(os.path.join(folder, "script.py"), "w", encoding="utf-8") as f:
        f.write(code)
    meta = {
        "id": f"{KAGGLE_USERNAME}/{slug}",
        "title": slug,
        "code_file": "script.py",
        "language": "python",
        "kernel_type": "script",
        "is_private": "true",
        "enable_gpu": "true" if gpu else "false",
        "enable_internet": "true",
    }
    with open(os.path.join(folder, "kernel-metadata.json"), "w") as f:
        json.dump(meta, f)
    api.kernels_push(folder)


def run(force, slug, gpu, ngrok_token):
    status = st.empty()
    box = st.empty()

    api = KaggleApi()
    api.authenticate()

    # ၁။ အရင် link သုံးလို့ရသေးလား
    if not force:
        links, ready, error, _ = read_state()
        alive = {k: v for k, v in links.items() if is_alive(v)}
        if alive:
            status.success("♻️ အရင် link သုံးလို့ရသေးတယ် — အသစ်မထုတ်ပါ")
            show_final(alive)
            return

    # ၂။ Kaggle session run နေသေးလား
    pushed = False
    t_push = 0
    if not force and kernel_busy(api, slug):
        status.info("⏳ Kaggle session run/စတင်နေတုန်းပါ — link စောင့်နေတယ်...")
    else:
        try:
            push_kernel(api, slug, gpu, ngrok_token)
        except Exception as e:
            status.error(f"Push မအောင်မြင်ပါ: {e}")
            return
        pushed = True
        t_push = time.time()
        status.info("⏳ Kaggle စတင်နေတယ်...")

    # ၃။ link အသစ် စောင့်မယ် (၂ စက္ကန့်တစ်ခါ၊ ၁၀ မိနစ်အထိ)
    for _ in range(300):
        links, ready, error, start_t = read_state()
        fresh = (start_t >= t_push - 10) if pushed else bool(start_t)
        if fresh and links:
            box.markdown(links_md(links))
            if not ready:
                status.info("⏳ Link ရပါပြီ၊ App စတက်နေတယ်... ခဏနေမှ ဖွင့်ပါ")
        if fresh and error:
            status.error(f"❌ Kaggle မှာ error: {error}")
            return
        if fresh and ready and links:
            alive = {k: v for k, v in links.items() if is_alive(v)}
            if alive:
                status.success("✅ App အဆင်သင့်ဖြစ်ပါပြီ! VPN မလိုဘဲ ပွင့်တဲ့ link ကို သုံးပါ")
                box.empty()
                show_final(alive)
                return
        time.sleep(2)

    if pushed:
        status.warning("မအောင်မြင်သေးပါ။ Kaggle → Your Work → Logs ကို စစ်ကြည့်ပါ။")
    else:
        status.warning(
            "Kaggle session ကျန်နေပေမဲ့ link မရပါ။ Kaggle မှာ Stop နှိပ်ပါ၊ "
            "ဒါမှမဟုတ် '🔄 အသစ်အတင်းထုတ်မယ်' ကို နှိပ်ပါ။"
        )


# ------------------------------------------------------------ UI
slug = st.text_input("Kernel နာမည် (အင်္ဂလိပ်စာလုံး၊ ဂဏန်း၊ - သာ)", "my-link-runner")
gpu = st.checkbox("GPU ဖွင့်မယ်", value=True)
ngrok_token = st.text_input("ngrok authtoken (မရှိရင် ကျော်ပါ)", type="password")

if st.button("🚀 Link ယူမယ် (ရှိပြီးသား သုံးလို့ရရင် ပြန်သုံးမယ်)"):
    run(False, slug, gpu, ngrok_token)

if st.button("🔄 အသစ်အတင်းထုတ်မယ်"):
    run(True, slug, gpu, ngrok_token)