import os, json, time, tempfile
import requests
import streamlit as st

# ==========================================
# ⚙️ Settings (Key & Username ထည့်ပြီးသား)
# ==========================================
KAGGLE_USERNAME = "thetuaiaa"
KAGGLE_KEY = "KGAT_28b2b967d309484510ffc764b8130e69"

SLUG = "my-link-runner"
GPU_ENABLED = False  # CPU နဲ့ Run ရန်
TOPIC = "kgl-k-7f3a9c2e51b84d06"
NGROK_TOKEN = ""  # ngrok သုံးချင်ရင် authtoken ဒီမှာထည့် (မထည့်ရင် ngrok ကျော်မယ်)

os.environ["KAGGLE_USERNAME"] = KAGGLE_USERNAME
os.environ["KAGGLE_KEY"] = KAGGLE_KEY
os.environ["KAGGLE_API_TOKEN"] = KAGGLE_KEY

from kaggle.api.kaggle_api_extended import KaggleApi

st.set_page_config(page_title="Kaggle Multi Link", page_icon="🔗")
st.title("🔗 Kaggle Multi-Tunnel Link ထုတ်စက်")

# ==========================================
# Kaggle မှာ Run မယ့် Script
# ==========================================
KAGGLE_SCRIPT = r'''
import os, re, sys, time, subprocess, threading, socket, shutil
from importlib import metadata
import requests

NTFY_TOPIC = "__TOPIC__"
NGROK_TOKEN = "__NGROK__"
REPO_URL = "https://github.com/Thetpaing467/new.git"
REPO_DIR = "/kaggle/working/new"
APP_FILE = "app.py"
PORT = 7860
LOG = "/kaggle/working/app.log"
WORK = "/kaggle/working"
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
        "openssh-client",
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
    say("apt ✅ (ffmpeg / fonts / ssh ပြီး)")

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
        "MyanmarPadaung.ttf" if "MyanmarPadaung.ttf" in fonts else sorted(fonts)[0]
    )
os.environ["GRADIO_ANALYTICS_ENABLED"] = "False"
os.environ["GRADIO_SERVER_PORT"] = str(PORT)

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
say("app စတင်နေတယ်...")

# ---------------------------------------------------------- Tunnels
SEEN = set()
LOCK = threading.Lock()

def publish(name, url):
    with LOCK:
        if name in SEEN:
            return
        SEEN.add(name)
    say(f"{name} ✅ {url}")
    post("link", f"{name}={url}")
    post("ready", "1")

def wait_port(port, timeout=900):
    t = time.time()
    while time.time() - t < timeout:
        if app_proc.poll() is not None:
            return False
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return True
        except OSError:
            time.sleep(0.5)
    return False

def run_tunnel(name, cmd, pattern, timeout=150, fmt="{}"):
    log = f"{WORK}/tun_{name}.log"
    try:
        p = subprocess.Popen(
            cmd, shell=True, stdin=subprocess.PIPE,
            stdout=open(log, "w"), stderr=subprocess.STDOUT,
        )
    except Exception as e:
        say(f"{name} ❌ {e}")
        return
    rx = re.compile(pattern)
    t = time.time()
    while time.time() - t < timeout:
        try:
            txt = open(log, encoding="utf-8", errors="ignore").read()
        except Exception:
            txt = ""
        m = rx.search(txt)
        if m:
            publish(name, fmt.format(m.group(0)))
            return
        if p.poll() is not None:
            break
        time.sleep(1)
    say(f"{name} ❌ link မရပါ")

def download(url, dest):
    rc, out = sh(f"curl -fsSL -o '{dest}' '{url}'")
    return rc == 0

SSH_OPTS = (
    "-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "
    "-o ServerAliveInterval=30 -o ExitOnForwardFailure=yes"
)

def tun_cloudflare():
    b = f"{WORK}/cloudflared"
    if not os.path.exists(b):
        if not download(
            "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64", b
        ):
            say("cloudflared download ❌")
            return
        os.chmod(b, 0o755)
    run_tunnel(
        "cloudflare",
        f"{b} tunnel --url http://localhost:{PORT} --no-autoupdate",
        r"https://[a-zA-Z0-9\-]+\.trycloudflare\.com",
    )

def tun_pinggy():
    run_tunnel(
        "pinggy",
        f"ssh {SSH_OPTS} -p 443 -R0:localhost:{PORT} a.pinggy.io",
        r"https://[a-zA-Z0-9\-\.]+\.pinggy\.(?:link|online)",
    )

def tun_localhostrun():
    run_tunnel(
        "localhost.run",
        f"ssh {SSH_OPTS} -R 80:localhost:{PORT} nokey@localhost.run",
        r"https://[a-zA-Z0-9\-]+\.(?:lhr\.life|localhost\.run)",
    )

def tun_serveo():
    run_tunnel(
        "serveo",
        f"ssh {SSH_OPTS} -R 80:localhost:{PORT} serveo.net",
        r"https://[a-zA-Z0-9\-]+\.serveo(?:usercontent)?\.(?:net|com)",
    )

def tun_localtunnel():
    if not shutil.which("npx"):
        say("localtunnel ❌ node/npx မရှိပါ")
        return
    run_tunnel(
        "localtunnel",
        f"npx --yes localtunnel --port {PORT}",
        r"https://[a-zA-Z0-9\-]+\.loca\.lt",
        timeout=180,
    )

def tun_bore():
    b = f"{WORK}/bore"
    if not os.path.exists(b):
        tgz = f"{WORK}/bore.tgz"
        if not download(
            "https://github.com/ekzhang/bore/releases/download/v0.5.1/bore-v0.5.1-x86_64-unknown-linux-musl.tar.gz",
            tgz,
        ):
            say("bore download ❌")
            return
        sh(f"tar -xzf {tgz} -C {WORK}")
        os.chmod(b, 0o755)
    run_tunnel("bore", f"{b} local {PORT} --to bore.pub", r"bore\.pub:\d+")

def tun_ngrok():
    if not NGROK_TOKEN:
        say("ngrok ကျော် (token မထည့်ထား)")
        return
    try:
        sh(f"{sys.executable} -m pip install -q pyngrok")
        from pyngrok import ngrok
        ngrok.set_auth_token(NGROK_TOKEN)
        publish("ngrok", ngrok.connect(PORT).public_url)
    except Exception as e:
        say(f"ngrok ❌ {e}")

def gradio_watch():
    rx = re.compile(r"https://[a-zA-Z0-9\-]+\.gradio\.live")
    while True:
        m = rx.search(tail_log(8000))
        if m:
            publish("gradio", m.group(0))
            return
        if app_proc.poll() is not None:
            return
        time.sleep(0.5)

def start_tunnels():
    t_apt.join()  # ssh / node အတွက် apt ပြီးအောင်စောင့်
    if not wait_port(PORT):
        return
    say("app port ပွင့်ပြီ — tunnels စတင်နေတယ်")
    for fn in (tun_cloudflare, tun_pinggy, tun_localhostrun, tun_serveo,
               tun_localtunnel, tun_bore, tun_ngrok):
        threading.Thread(target=fn, daemon=True).start()

threading.Thread(target=gradio_watch, daemon=True).start()
threading.Thread(target=start_tunnels, daemon=True).start()

# ပထမဆုံး link မရမချင်း စောင့် (အများဆုံး ၁၀ မိနစ်)
for _ in range(2000):
    if app_proc.poll() is not None:
        print(f"❌ App crash (exit {app_proc.returncode})")
        print(tail_log())
        post("error", "App crash: " + tail_log(400))
        raise SystemExit("App crash")
    if SEEN:
        break
    time.sleep(0.3)

if not SEEN:
    print("⚠️ Link တစ်ခုမှ မထွက်ပါ — log:\n")
    print(tail_log())
    post("error", "Link မထွက်ပါ: " + tail_log(400))
    raise SystemExit("Link မထွက်လို့ ရပ်လိုက်တယ်။")

print(f"Running... links: {sorted(SEEN)}")
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
                links[name] = url
            elif kind == "ready":
                ready = True
            elif kind == "error":
                error = val
    except Exception:
        pass
    return links, ready, error, start_t

def is_alive(url):
    if not url.startswith("http"):
        return True  # bore လိုမျိုး http မဟုတ်တာတွေ
    try:
        r = requests.get(url, timeout=10, allow_redirects=True)
        return r.status_code in (200, 401, 403)
    except Exception:
        return False

def kernel_busy(api):
    try:
        api.kernels_list(user=KAGGLE_USERNAME, page=1, page_size=100)
        return False
    except Exception as e:
        print("kernel_busy error:", e)
        return False

def push_kernel(api):
    code = KAGGLE_SCRIPT.replace("__TOPIC__", TOPIC).replace("__NGROK__", NGROK_TOKEN)
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

def render(box, links):
    with box.container():
        for name, url in links.items():
            if url.startswith("http"):
                st.markdown(f"**{name}** → [{url}]({url})")
            else:
                st.markdown(f"**{name}** → `{url}`")
            st.code(url)

def run(force):
    status, box = st.empty(), st.empty()
    api = KaggleApi()
    api.authenticate()

    if not force:
        links, _, _, _ = read_state()
        alive = {k: v for k, v in links.items() if is_alive(v)}
        if alive:
            status.success("♻️ အရင် Link တွေ သုံးလို့ရသေးတယ် — အသစ်မထုတ်ပါ")
            render(box, alive)
            return

    pushed, t_push = False, 0
    if not force and kernel_busy(api):
        status.info("⏳ Kaggle session run/စတင်နေတုန်းပါ — link စောင့်နေတယ်...")
    else:
        try:
            push_kernel(api)
        except Exception as e:
            status.error(f"Push မအောင်မြင်ပါ: {e}")
            return
        pushed, t_push = True, time.time()
        status.info("⏳ Kaggle စတင်နေတယ်... (Link အမျိုးမျိုး ထုတ်နေတယ်)")

    fresh_after = (t_push - 10) if pushed else 0
    first_t = None

    for _ in range(600):
        links, ready, error, start_t = read_state()
        fresh = start_t > 0 and start_t >= fresh_after

        if fresh and error and not links:
            status.error(f"❌ Kaggle မှာ error: {error}")
            return

        if fresh and links:
            if first_t is None:
                first_t = time.time()
                status.success("✅ Link ရပါပြီ! (ကျန်တဲ့ link တွေ ဆက်စောင့်နေတယ်...)")
            render(box, links)
            if time.time() - first_t > 90:
                status.success(f"✅ ပြီးပါပြီ — Link {len(links)} ခု ရပါတယ်")
                return

        time.sleep(2)

    if first_t is None:
        status.warning("မအောင်မြင်သေးပါ။ Kaggle → Your Work → Logs ကို စစ်ကြည့်ပါ။")

# ==========================================
# Streamlit UI
# ==========================================
st.warning("⚠️ ဒီ app မှာ Kaggle API Token ကို hardcode ထည့်ထားပါတယ်။ Public မှာ မတင်ပါနဲ့။")
st.info(
    "🚀 Gradio (`.gradio.live`) + Cloudflare + Pinggy + localhost.run + Serveo + "
    "localtunnel + bore (+ ngrok token ထည့်ရင်) link တွေ တစ်ပြိုင်နက် ထုတ်ပေးမယ်။"
)

if st.button("🚀 Link ယူမယ်"):
    run(False)

if st.button("🔄 အသစ်အတင်းထုတ်မယ်"):
    run(True)
