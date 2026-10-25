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


def notify(text):
    try:
        requests.post(f"https://ntfy.sh/{NTFY_TOPIC}", data=text.encode("utf-8"), timeout=15)
    except Exception as e:
        print("ntfy error:", e)


sh("pkill -f '[c]loudflared tunnel' ; pkill -f '[p]ython.*app.py'")
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
        sh(f"wget -q -O {CF} https://github.com/cloudflare/cloudflared/releases/latest/"
           f"download/cloudflared-linux-amd64 && chmod +x {CF}")
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


t_git = threading.Thread(target=task_git)
t_pip = threading.Thread(target=task_pip)
t_apt = threading.Thread(target=task_apt)
t_cf = threading.Thread(target=task_cf)
t_tun = threading.Thread(target=task_tunnel, daemon=True)
for t in (t_git, t_pip, t_apt, t_cf, t_tun):
    t.start()

t_git.join()
t_pip.join()
assert RES.get("git", (1,))[0] == 0, "git clone/update မအောင်မြင်ပါ"
os.chdir(REPO_DIR)
print("Repo files:", sorted(os.listdir(".")))
assert os.path.exists(APP_FILE), "app.py repo ထဲမှာ ရှိရမယ်"

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
        break
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{PORT}", timeout=1)
        started = True
        say("app ✅")
        break
    except Exception:
        time.sleep(0.5)
else:
    print("⚠️ App မတက်သေးဘူး — log:\n")
    print(tail_log())

if not started:
    raise SystemExit("App မတက်လို့ ရပ်လိုက်တယ်။")

if url_ready.wait(timeout=60):
    print("\n🌐 PUBLIC LINK:", tunnel_url["u"], "\n", flush=True)
    notify(tunnel_url["u"])
else:
    print("⚠️ Tunnel link မရဘူး")

print(f"Running... log: {LOG}")
while True:
    time.sleep(30)
    if app_proc.poll() is not None:
        print(f"❌ App ရပ်သွားပြီ (exit {app_proc.returncode}) — log:\n")
        print(tail_log())
        break
'''

slug = st.text_input("Kernel နာမည် (အင်္ဂလိပ်စာလုံး၊ ဂဏန်း၊ - သာ)", "my-link-runner")
gpu = st.checkbox("GPU ဖွင့်မယ်", value=True)

if st.button("🚀 Kaggle မှာ run ပြီး Link ယူမယ်"):
    topic = "kg-" + uuid.uuid4().hex[:12]
    code = KAGGLE_SCRIPT.replace("__TOPIC__", topic)

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

    link = None
    with st.spinner("Kaggle မှာ run နေတယ်... Link စောင့်နေတယ် (၃–၈ မိနစ်ကြာနိုင်)"):
        for _ in range(120):  # 5s × 120 = 10 မိနစ်
            try:
                r = requests.get(
                    f"https://ntfy.sh/{topic}/json?poll=1&since=all", timeout=10
                )
                for line in r.text.strip().splitlines():
                    msg = json.loads(line).get("message")
                    if msg and msg.startswith("https://"):
                        link = msg
            except Exception:
                pass
            if link:
                break
            time.sleep(5)

    if link:
        st.success("✅ အောင်မြင်ပါတယ်!")
        st.markdown(f"🔗 **Public Link:** [{link}]({link})")
        st.code(link)
    else:
        st.warning("Link မရသေးပါ။ Kaggle → Your Work → my-link-runner → Logs ကို စစ်ကြည့်ပါ။")