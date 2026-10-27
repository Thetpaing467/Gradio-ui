import os, json, time, tempfile
import requests
import streamlit as st

KAGGLE_USERNAME = "thetuaiaa"
KAGGLE_KEY = "e949c9ede1ed6d03eda8811b5421a262"
SLUG = "my-link-runner"
GPU_ENABLED = False   # GPU လိုရင် True ပြောင်းပါ (တန်းစီရလို့ နှေးနိုင်)
TOPIC = "kgl-k-7f3a9c2e51b84d06"

os.environ["KAGGLE_USERNAME"] = KAGGLE_USERNAME
os.environ["KAGGLE_KEY"] = KAGGLE_KEY
from kaggle.api.kaggle_api_extended import KaggleApi

NAMES = {
    "pinggy": "Pinggy",
    "lhr": "localhost.run",
    "serveo": "Serveo",
    "cloudflare": "Cloudflare",
    "tmole": "Tunnelmole",
    "ngrok": "ngrok",
}

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


post("start", "1")

sh("pkill -f '[c]loudflared tunnel' ; pkill -f '[t]mole' ; pkill -f '[p]ython.*app.py'")
time.sleep(1)

# ---------------------------------------------------------- tunnels (အစမှာတင် စ)
def run_ssh(name, args, pattern):
    if sh("which ssh")[0] != 0:
        sh("apt-get update -qq && apt-get install -y -qq openssh-client")
    p = subprocess.Popen(
        ["ssh",
         "-o", "StrictHostKeyChecking=no",
         "-o", "UserKnownHostsFile=/dev/null",
         "-o", "ServerAliveInterval=30"] + args,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True)
    sent = False
    for line in p.stdout:
        line = ANSI.sub("", line)
        m = re.search(pattern, line)
        if m and not sent:
            sent = True
            say(f"{name} ✅")
            post(name, m.group(0))


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


def run_tmole():
    try:
        if sh("which tmole")[0] != 0:
            if sh("which npm")[0] != 0:
                sh("apt-get update -qq && DEBIAN_FRONTEND=noninteractive "
                   "apt-get install -y -qq nodejs npm")
            sh("npm install -g tunnelmole")
        if sh("which tmole")[0] != 0:
            say("tmole ❌ (install မရ)")
            return
        p = subprocess.Popen(
            ["tmole", str(PORT)],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        sent = False
        for line in p.stdout:
            line = ANSI.sub("", line)
            m = re.search(r"https://[a-z0-9\-]+\.tunnelmole\.(?:net|com)", line)
            if m and not sent:
                sent = True
                say("tmole ✅")
                post("tmole", m.group(0))
    except Exception as e:
        say(f"tmole ❌ {e}")


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


TUNNELS = [
    ("pinggy", ["-p", "443", f"-R0:localhost:{PORT}", "a.pinggy.io"],
     r"https://[a-zA-Z0-9\-\.]+pinggy\.(?:link|io|online)"),
    ("lhr", ["-R", f"80:localhost:{PORT}", "nokey@localhost.run"],
     r"https://[a-z0-9\-]+\.lhr\.life"),
    ("serveo", ["-R", f"80:localhost:{PORT}", "serveo.net"],
     r"https://[a-z0-9\-]+\.serveo(?:usercontent)?\.(?:net|com)"),
]
for name, args, pattern in TUNNELS:
    threading.Thread(target=run_ssh, args=(name, args, pattern), daemon=True).start()
threading.Thread(target=run_cloudflared, daemon=True).start()
threading.Thread(target=run_tmole, daemon=True).start()
threading.Thread(target=run_ngrok, daemon=True).start()

# ---------------------------------------------------------- app ပြင်ဆင်ခြင်း
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


# ------------------------------------------------------------ helpers
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


def kernel_busy(api):
    try:
        res = api.kernels_status(f"{KAGGLE_USERNAME}/{SLUG}")
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


def push_kernel(api, ngrok_token):
    code = (KAGGLE_SCRIPT.replace("__TOPIC__", TOPIC)
                         .replace("__NGROK__", ngrok_token.strip()))
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


def run(force, ngrok_token):
    status, box = st.empty(), st.empty()
    api = KaggleApi()
    api.authenticate()

    # ၁။ အရင် link သုံးလို့ရသေးရင် ပြန်သုံး
    if not force:
        links, _, _, _ = read_state()
        alive = {k: v for k, v in links.items() if is_alive(v)}
        if alive:
            status.success("♻️ အရင် link သုံးလို့ရသေးတယ် — အသစ်မထုတ်ပါ")
            show_final(alive)
            return

    # ၂။ Kaggle session run နေရင် push မလုပ်ဘဲ စောင့်
    pushed, t_push = False, 0
    if not force and kernel_busy(api):
        status.info("⏳ Kaggle session run/စတင်နေတုန်းပါ — link စောင့်နေတယ်...")
    else:
        try:
            push_kernel(api, ngrok_token)
        except Exception as e:
            status.error(f"Push မအောင်မြင်ပါ: {e}")
            return
        pushed, t_push = True, time.time()
        status.info("⏳ Kaggle စတင်နေတယ်...")

    fresh_after = (t_push - 10) if pushed else 0

    # ၃။ link စောင့် (၂ စက္ကန့်တစ်ခါ၊ ၁၀ မိနစ်အထိ)
    for _ in range(300):
        links, ready, error, start_t = read_state()
        fresh = start_t > 0 and start_t >= fresh_after
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
                status.success("✅ App အဆင်သင့်ဖြစ်ပါပြီ! VPN ပိတ်ပြီး တစ်ခုချင်း စမ်းကြည့်ပါ")
                box.empty()
                show_final(alive)
                return
        time.sleep(2)

    status.warning("မအောင်မြင်သေးပါ။ Kaggle → Your Work → Logs ကို စစ်ကြည့်ပါ။")


# ------------------------------------------------------------ UI
with st.expander("⚙️ ngrok (ရွေးချယ်)"):
    ngrok_token = st.text_input("ngrok authtoken (မရှိရင် ကျော်ပါ)", type="password")

if st.button("🚀 Link ယူမယ် (ရှိပြီးသား သုံးလို့ရရင် ပြန်သုံးမယ်)"):
    run(False, ngrok_token)

if st.button("🔄 အသစ်အတင်းထုတ်မယ်"):
    run(True, ngrok_token)
