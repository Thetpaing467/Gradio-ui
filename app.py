import os, json, time, tempfile
import requests
import streamlit as st

KAGGLE_USERNAME = "thetuaiaa"
KAGGLE_KEY = "e949c9ede1ed6d03eda8811b5421a262"
SLUG = "my-link-runner"
GPU_ENABLED = False   # app crash ဖြစ်ရင် True ပြောင်းကြည့်ပါ
TOPIC = "kgl-k-7f3a9c2e51b84d06"
SUBDOMAIN = ""        # ပုံသေနာမည်မလိုရင် ဗလာထားပါ (random link ရမယ်)

os.environ["KAGGLE_USERNAME"] = KAGGLE_USERNAME
os.environ["KAGGLE_KEY"] = KAGGLE_KEY
from kaggle.api.kaggle_api_extended import KaggleApi

st.set_page_config(page_title="Serveo Link ထုတ်စက်", page_icon="🔗")
st.title("🔗 Public Link ထုတ်စက် (Serveo)")

KAGGLE_SCRIPT = r'''
import os, re, sys, time, subprocess, threading, urllib.request
from importlib import metadata
import requests

NTFY_TOPIC = "__TOPIC__"
SUB = "__SUB__"
REPO_URL = "https://github.com/Thetpaing467/new.git"
REPO_DIR = "/kaggle/working/new"
APP_FILE = "app.py"
PORT = 7860
LOG = "/kaggle/working/app.log"
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

sh("pkill -f '[p]ython.*app.py'")
time.sleep(1)


# ---------------------------------------------------------- Serveo tunnel (အစမှာတင် စ)
def run_serveo():
    if sh("which ssh")[0] != 0:
        sh("apt-get update -qq && apt-get install -y -qq openssh-client")
    fails = 0
    while True:   # ပြတ်သွားရင် ပြန်ချိတ်မယ်
        use_fixed = bool(SUB) and fails < 3
        target = f"{SUB}:80:localhost:{PORT}" if use_fixed else f"80:localhost:{PORT}"
        say(f"serveo ချိတ်နေတယ် ({'ပုံသေ ' + SUB if use_fixed else 'random'})")
        p = subprocess.Popen(
            ["ssh",
             "-o", "StrictHostKeyChecking=no",
             "-o", "UserKnownHostsFile=/dev/null",
             "-o", "ServerAliveInterval=30",
             "-o", "ExitOnForwardFailure=yes",
             "-R", target, "serveo.net"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True)
        state = {"got": False}
        # ၄၀ စက္ကန့်အတွင်း link မရရင် ssh ကို သတ်ပြီး ပြန်စ
        timer = threading.Timer(40, lambda: None if state["got"] else p.kill())
        timer.daemon = True
        timer.start()
        for line in p.stdout:
            line = ANSI.sub("", line)
            print(line, end="", flush=True)
            m = re.search(r"https://[a-z0-9\-]+\.serveo(?:usercontent)?\.(?:net|com)", line)
            if m and not state["got"]:
                state["got"] = True
                say("serveo ✅")
                post("serveo", m.group(0))
        timer.cancel()
        p.wait()
        fails = 0 if state["got"] else fails + 1
        say("serveo ပြတ်သွားတယ် — ပြန်ချိတ်မယ်")
        time.sleep(3 if state["got"] else 5)


threading.Thread(target=run_serveo, daemon=True).start()

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
    link, ready, error, start_t = None, False, None, 0
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
                link, ready, error, start_t = None, False, None, d.get("time", 0)
            elif kind == "serveo":
                link = val
            elif kind == "ready":
                ready = True
            elif kind == "error":
                error = val
    except Exception:
        pass
    return link, ready, error, start_t


def is_alive(url):
    try:
        r = requests.get(url, timeout=8)
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


def show_link(link):
    st.markdown(f"🔗 **Public Link:** [{link}]({link})")
    st.code(link)


def push_kernel(api):
    code = KAGGLE_SCRIPT.replace("__TOPIC__", TOPIC).replace("__SUB__", SUBDOMAIN)
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


def run(force):
    status = st.empty()
    api = KaggleApi()
    api.authenticate()

    # ၁။ အရင် link သုံးလို့ရသေးရင် ပြန်သုံး
    if not force:
        link, _, _, _ = read_state()
        if link and is_alive(link):
            status.success("♻️ အရင် link သုံးလို့ရသေးတယ် — အသစ်မထုတ်ပါ")
            show_link(link)
            return

    # ၂။ Kaggle session run နေရင် push မလုပ်ဘဲ စောင့်
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
        status.info("⏳ Kaggle စတင်နေတယ်...")

    fresh_after = (t_push - 10) if pushed else 0
    ready_polls = 0

    # ၃။ စောင့် (၂ စက္ကန့်တစ်ခါ၊ ၁၀ မိနစ်အထိ)
    for _ in range(300):
        link, ready, error, start_t = read_state()
        fresh = start_t > 0 and start_t >= fresh_after

        if fresh and error:
            status.error(f"❌ Kaggle မှာ error: {error}")
            return

        if fresh and link and not ready:
            status.info("⏳ Tunnel ရပါပြီ၊ App စတက်နေတယ်... "
                        "အဆင်သင့်ဖြစ်မှ link ကို ပြပါမယ် (၁–၃ မိနစ်)")

        if fresh and ready and link:
            if is_alive(link):
                status.success("✅ App အဆင်သင့်ဖြစ်ပါပြီ!")
                show_link(link)
                return
            ready_polls += 1
            status.info("⏳ App တက်ပြီ၊ Link ချိတ်ဆက်မှု စစ်နေတယ်...")
            if ready_polls >= 20:   # ၄၀ စက္ကန့်လောက် စစ်လို့မရရင် link ကို ပြမယ်
                status.warning("⚠️ Streamlit ကနေ စစ်လို့မရပေမဲ့ link ကို ကိုယ်တိုင် စမ်းကြည့်ပါ")
                show_link(link)
                return
        time.sleep(2)

    status.warning("မအောင်မြင်သေးပါ။ Kaggle → Your Work → Logs ကို စစ်ကြည့်ပါ။")


# ------------------------------------------------------------ UI
if st.button("🚀 Link ယူမယ် (ရှိပြီးသား သုံးလို့ရရင် ပြန်သုံးမယ်)"):
    run(False)

if st.button("🔄 အသစ်အတင်းထုတ်မယ်"):
    run(True)