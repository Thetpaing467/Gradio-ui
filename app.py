import os, json, time, uuid, tempfile
import requests
import streamlit as st

KAGGLE_USERNAME = "thetuaiaa"
KAGGLE_KEY = "e949c9ede1ed6d03eda8811b5421a262"

os.environ["KAGGLE_USERNAME"] = KAGGLE_USERNAME
os.environ["KAGGLE_KEY"] = KAGGLE_KEY
from kaggle.api.kaggle_api_extended import KaggleApi

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


sh("pkill -f '[c]loudflared tunnel' ; pkill -f '[p]ython.*app.py'")
time.sleep(1)

# ------------------------------------------------ tunnels (app မတက်ခင်ကတည်းက စ)
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

# ------------------------------------------------ app ပြင်ဆင်ခြင်း
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

NAMES = {"pinggy": "Pinggy", "cloudflare": "Cloudflare", "ngrok": "ngrok"}

slug = st.text_input("Kernel နာမည် (အင်္ဂလိပ်စာလုံး၊ ဂဏန်း၊ - သာ)", "my-link-runner")
gpu = st.checkbox("GPU ဖွင့်မယ်", value=True)
ngrok_token = st.text_input("ngrok authtoken (မရှိရင် ကျော်ပါ)", type="password")

if st.button("🚀 Kaggle မှာ run ပြီး Link ယူမယ်"):
    topic = "kg-" + uuid.uuid4().hex[:12]
    code = (KAGGLE_SCRIPT.replace("__TOPIC__", topic)
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

    api = KaggleApi()
    api.authenticate()
    try:
        api.kernels_push(folder)
    except Exception as e:
        st.error(f"Push မအောင်မြင်ပါ: {e}")
        st.stop()

    status = st.empty()
    box = st.empty()
    links, ready, error = {}, False, None

    status.info("⏳ Kaggle စတင်နေတယ်...")
    for _ in range(300):  # 2s × 300 = 10 မိနစ်
        try:
            r = requests.get(
                f"https://ntfy.sh/{topic}/json?poll=1&since=all", timeout=10
            )
            for line in r.text.strip().splitlines():
                msg = json.loads(line).get("message", "")
                if "|" not in msg:
                    continue
                kind, val = msg.split("|", 1)
                if kind in NAMES:
                    links[kind] = val
                elif kind == "ready":
                    ready = True
                elif kind == "error":
                    error = val
        except Exception:
            pass

        if links:
            box.markdown("\n\n".join(
                f"🔗 **{NAMES[k]}:** [{v}]({v})" for k, v in links.items()))
            if not ready:
                status.info("⏳ Link ရပါပြီ၊ App စတက်နေတယ်... ခဏနေမှ ဖွင့်ပါ")
        if ready and links:
            status.success("✅ App အဆင်သင့်ဖြစ်ပါပြီ! VPN မလိုဘဲ ပွင့်တဲ့ link ကို သုံးပါ")
            break
        if error:
            status.error(f"❌ Kaggle မှာ error: {error}")
            break
        time.sleep(2)
    else:
        status.warning("မအောင်မြင်သေးပါ။ Kaggle → Your Work → my-link-runner → Logs ကို စစ်ကြည့်ပါ။")

    for k, v in links.items():
        st.caption(NAMES[k])
        st.code(v)