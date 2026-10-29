import os, json, time, tempfile
import requests
import streamlit as st

# ---------------- ဒီနေရာ ပြင်ပါ ----------------
KAGGLE_USERNAME = "thetuaiaa"
KAGGLE_KEY = "e949c9ede1ed6d03eda8811b5421a262"   # key အသစ်ထုတ်ခဲ့ရင် ဒီနေရာမှာ အစားထိုးပါ
SLUG = "my-link-runner"
GPU_ENABLED = False   # app crash ဖြစ်ရင် True ပြောင်းကြည့်ပါ
TOPIC = "kgl-k-7f3a9c2e51b84d06"
SUBDOMAIN = ""        # Serveo ပုံသေနာမည်မလိုရင် ဗလာထားပါ
NGROK_TOKEN = ""      # ngrok account token ရှိရင်ထည့်ပါ (မရှိရင် ဗလာ)
PINGGY_TOKEN = ""     # pinggy.io account token ရှိရင်ထည့်ပါ (မရှိရင် ဗလာ)
# -----------------------------------------------

os.environ["KAGGLE_USERNAME"] = KAGGLE_USERNAME
os.environ["KAGGLE_KEY"] = KAGGLE_KEY
from kaggle.api.kaggle_api_extended import KaggleApi

st.set_page_config(page_title="Link ထုတ်စက်", page_icon="🔗")
st.title("🔗 Public Link ထုတ်စက် (Multi Tunnel)")

KAGGLE_SCRIPT = r'''
import os, re, sys, time, subprocess, threading, urllib.request, tarfile, stat
from importlib import metadata
import requests

NTFY_TOPIC = "__TOPIC__"
SUB = "__SUB__"
NGROK_TOKEN = "__NGROK__"
PINGGY_TOKEN = "__PINGGY__"
REPO_URL = "https://github.com/Thetpaing467/new.git"
REPO_DIR = "/kaggle/working/new"
APP_FILE = "app.py"
PORT = 7860
LOG = "/kaggle/working/app.log"
T0 = time.time()
ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
SSH_OPTS = ["-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            "-o", "ServerAliveInterval=30",
            "-o", "ServerAliveCountMax=3",
            "-o", "ExitOnForwardFailure=yes"]


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


# ============================================================ tunnel အားလုံး
def tunnel_loop(name, build_cmd, rx, fmt=None, wait=60, prep=None):
    """tunnel တစ်ခုကို run မယ်။ link ထွက်ရင် ntfy ပို့မယ်။ ပြတ်ရင် ပြန်ချိတ်မယ်။"""
    try:
        if prep and not prep():
            say(f"{name} ကျော်လိုက်တယ် (မအောင်မြင်)")
            return
    except Exception as e:
        say(f"{name} prep error: {e}")
        return
    rx = re.compile(rx)
    fails = 0
    while True:
        try:
            say(f"{name} ချိတ်နေတယ်")
            p = subprocess.Popen(build_cmd(), stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            state = {"got": False}
            timer = threading.Timer(wait, lambda: None if state["got"] else p.kill())
            timer.daemon = True
            timer.start()
            for line in p.stdout:
                line = ANSI.sub("", line)
                m = rx.search(line)
                if m:
                    url = fmt(m) if fmt else m.group(0)
                    state["got"] = True
                    say(f"{name} ✅ {url}")
                    post("tun", f"{name}={url}")
                elif not state["got"]:
                    print(f"[{name}] {line.rstrip()[:200]}", flush=True)
            timer.cancel()
            p.wait()
        except Exception as e:
            say(f"{name} error: {e}")
            state = {"got": False}
        fails = 0 if state["got"] else fails + 1
        say(f"{name} ပြတ်သွားတယ် — ပြန်ချိတ်မယ် (fail {fails})")
        if fails >= 6:
            say(f"{name} ၆ ကြိမ်ဆက်ရှုံး — ရပ်လိုက်တယ်")
            return
        time.sleep(3 if state["got"] else min(5 * fails, 30))


def need_ssh():
    if sh("which ssh")[0] != 0:
        sh("apt-get update -qq && apt-get install -y -qq openssh-client")
    return sh("which ssh")[0] == 0


NODE_LOCK = threading.Lock()


def need_node():
    with NODE_LOCK:
        if sh("which npx")[0] != 0:
            say("nodejs/npm သွင်းနေတယ်...")
            sh("apt-get update -qq")
            sh("DEBIAN_FRONTEND=noninteractive apt-get install -y -qq nodejs npm")
        return sh("which npx")[0] == 0


def wait_app_port():
    """app port တက်မှ tunnelmole စမယ် (မဟုတ်ရင် 'nothing running on port' နဲ့ ထွက်သွားတယ်)"""
    for _ in range(900):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}", timeout=2)
            return True
        except Exception:
            time.sleep(2)
    return False


def need_node_and_app():
    return need_node() and wait_app_port()


def download(url, dest):
    r = requests.get(url, timeout=120, stream=True, allow_redirects=True)
    r.raise_for_status()
    with open(dest, "wb") as f:
        for chunk in r.iter_content(1 << 20):
            f.write(chunk)


CF_BIN = "/kaggle/working/cloudflared"


def need_cloudflared():
    if not os.path.exists(CF_BIN):
        download("https://github.com/cloudflare/cloudflared/releases/latest/download/"
                 "cloudflared-linux-amd64", CF_BIN)
        os.chmod(CF_BIN, os.stat(CF_BIN).st_mode | stat.S_IEXEC)
    return True


BORE_BIN = "/kaggle/working/bore"


def need_bore():
    if not os.path.exists(BORE_BIN):
        tgz = "/kaggle/working/bore.tgz"
        download("https://github.com/ekzhang/bore/releases/download/v0.5.1/"
                 "bore-v0.5.1-x86_64-unknown-linux-musl.tar.gz", tgz)
        with tarfile.open(tgz) as t:
            t.extractall("/kaggle/working")
        os.chmod(BORE_BIN, os.stat(BORE_BIN).st_mode | stat.S_IEXEC)
    return True


def ngrok_thread():
    try:
        sh(f"{sys.executable} -m pip install -q pyngrok")
        from pyngrok import ngrok
        ngrok.set_auth_token(NGROK_TOKEN)
        while True:
            try:
                t = ngrok.connect(PORT, "http")
                url = t.public_url.replace("http://", "https://")
                say(f"ngrok ✅ {url}")
                post("tun", f"ngrok={url}")
                while True:
                    time.sleep(30)
                    if not ngrok.get_tunnels():
                        break
            except Exception as e:
                say(f"ngrok error: {e}")
                time.sleep(10)
    except Exception as e:
        say(f"ngrok ကျော်: {e}")


TUNNELS = [
    # (name, build_cmd, regex, fmt, wait, prep)
    ("pinggy",
     lambda: ["ssh"] + SSH_OPTS + ["-p", "443", f"-R0:localhost:{PORT}", "free.pinggy.io"],
     r"https://[a-z0-9\-]+\.(?:a\.)?free\.pinggy\.(?:link|online)", None, 60, need_ssh),
    ("localhost.run",
     lambda: ["ssh"] + SSH_OPTS + ["-R", f"80:localhost:{PORT}", "nokey@localhost.run"],
     r"https://[a-z0-9]+\.lhr\.life", None, 60, need_ssh),
    ("serveo",
     lambda: ["ssh"] + SSH_OPTS + ["-R", (f"{SUB}:80:localhost:{PORT}" if SUB else f"80:localhost:{PORT}"),
                                   "serveo.net"],
     r"https://(?!console\.)[a-z0-9\-]+\.serveousercontent\.com", None, 40, need_ssh),
    ("cloudflare",
     lambda: [CF_BIN, "tunnel", "--url", f"http://localhost:{PORT}",
              "--no-autoupdate", "--protocol", "http2"],
     r"https://[a-z0-9\-]+\.trycloudflare\.com", None, 90, need_cloudflared),
    ("bore",
     lambda: [BORE_BIN, "local", str(PORT), "--to", "bore.pub"],
     r"bore\.pub:(\d+)", lambda m: f"http://bore.pub:{m.group(1)}", 60, need_bore),
    ("tunnelmole",
     lambda: ["npx", "--yes", "tunnelmole", str(PORT)],
     r"https://[a-z0-9\-]+\.tunnelmole\.(?:net|com)", None, 120, need_node_and_app),
    ("localtunnel",
     lambda: ["npx", "--yes", "localtunnel", "--port", str(PORT)],
     r"https://[a-z0-9\-]+\.loca\.lt", None, 120, need_node),
]

if PINGGY_TOKEN:
    TUNNELS.append(
        ("pinggy-token",
         lambda: ["ssh"] + SSH_OPTS + ["-p", "443", f"-R0:localhost:{PORT}",
                                       f"{PINGGY_TOKEN}@pro.pinggy.io"],
         r"https://[a-z0-9\-\.]+\.pinggy\.(?:link|online)", None, 60, need_ssh))

for name, cmd, rx, fmt, wait, prep in TUNNELS:
    threading.Thread(target=tunnel_loop, args=(name, cmd, rx, fmt, wait, prep),
                     daemon=True).start()
if NGROK_TOKEN:
    threading.Thread(target=ngrok_thread, daemon=True).start()

# ============================================================ app ပြင်ဆင်ခြင်း
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


def gradio_share():
    """Gradio ရဲ့ ကိုယ်ပိုင် share tunnel (xxxx.gradio.live) ကို app မပြင်ဘဲ ထုတ်မယ်"""
    for _ in range(900):          # pip ပြီးတဲ့အထိ စောင့်
        if RES.get("pip"):
            break
        time.sleep(1)
    if not wait_app_port():
        say("gradio share ကျော် — app port မတက်")
        return
    fails = 0
    while fails < 6:
        try:
            import inspect, secrets
            from gradio import networking
            params = inspect.signature(networking.setup_tunnel).parameters
            kw = dict(local_host="127.0.0.1", local_port=PORT,
                      share_token=secrets.token_urlsafe(32),
                      share_server_address=None,
                      share_server_tls_certificate=None)
            kw = {k: v for k, v in kw.items() if k in params}
            url = networking.setup_tunnel(**kw)
            say(f"gradio ✅ {url}")
            post("tun", f"gradio={url}")
            fails = 0
            bad = 0
            while bad < 3:        # link သေသွားရင် ပြန်ထုတ်
                time.sleep(60)
                try:
                    r = requests.get(url, timeout=10)
                    bad = 0 if r.status_code < 500 else bad + 1
                except Exception:
                    bad += 1
            say("gradio link သေသွားတယ် — ပြန်ထုတ်မယ်")
        except Exception as e:
            fails += 1
            say(f"gradio share error ({fails}): {str(e)[:200]}")
            time.sleep(15)


threading.Thread(target=gradio_share, daemon=True).start()

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


def start_app():
    return subprocess.Popen([sys.executable, "-u", APP_FILE],
                            stdout=open(LOG, "a"), stderr=subprocess.STDOUT, env=env)


def app_ok(timeout=5):
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{PORT}", timeout=timeout)
        return True
    except Exception:
        return False


def wait_up(proc, secs=180):
    for _ in range(int(secs * 2)):
        if proc.poll() is not None or app_ok(1):
            break
        time.sleep(0.5)
    return app_ok()


app_proc = start_app()
say("app စတင်နေတယ်...")
if wait_up(app_proc, 180):
    say("app ✅")
    post("ready", "1")
else:
    print("⚠️ App မတက်သေးဘူး — log:\n")
    print(tail_log())
    post("error", "App မတက်ပါ: " + tail_log(400))

# ============================================================ watchdog
crashes, bad = 0, 0
print(f"Running... log: {LOG}")
while True:
    time.sleep(10)
    if app_proc.poll() is not None:
        crashes += 1
        say(f"❌ App ရပ်သွားတယ် (exit {app_proc.returncode}) — ပြန်စမယ် #{crashes}")
        print(tail_log(1500))
        time.sleep(min(5 * crashes, 30))
        app_proc = start_app()
        bad = 0
        if wait_up(app_proc, 120):
            say("app ပြန်တက်ပြီ ✅")
            post("ready", "1")
        continue
    # process ရှိပေမဲ့ မတုံ့ပြန်ရင် (hang) ၃ ကြိမ်ဆက်ရှုံးမှ သတ်မယ်
    bad = 0 if app_ok(8) else bad + 1
    if bad >= 3:
        say("⚠️ App hang ဖြစ်နေတယ် — kill ပြီး ပြန်စမယ်")
        app_proc.kill()
        bad = 0
'''


# ------------------------------------------------------------ helpers
def read_state():
    """ntfy ကနေ link အားလုံး (tunnel နာမည်အလိုက် နောက်ဆုံး link) ကို ဖတ်"""
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
            elif kind == "tun" and "=" in val:
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
    try:
        r = requests.get(url, timeout=8, allow_redirects=True)
        return r.status_code < 500 or r.status_code == 511
    except Exception:
        return False


def alive_links(links):
    return {n: u for n, u in links.items() if is_alive(u)}


def kernel_busy(api):
    try:
        res = api.kernels_status(f"{KAGGLE_USERNAME}/{SLUG}")
        s = str(getattr(res, "status", res)).lower()
        return "running" in s or "queued" in s
    except Exception:
        return False


def show_links(links, checked=None):
    st.markdown("### 🔗 Public Links")
    st.caption("ဖုန်းမှာ VPN ပိတ်ပြီး တစ်ခုချင်း နှိပ်စမ်းကြည့်ပါ၊ ဖွင့်လို့ရတာကို သုံးပါ။")
    for name, url in links.items():
        mark = ""
        if checked is not None:
            mark = " ✅" if name in checked else " ❔"
        st.markdown(f"**{name}**{mark}")
        st.markdown(f"[{url}]({url})")
        st.code(url)


def push_kernel(api):
    code = (KAGGLE_SCRIPT.replace("__TOPIC__", TOPIC)
            .replace("__SUB__", SUBDOMAIN)
            .replace("__NGROK__", NGROK_TOKEN)
            .replace("__PINGGY__", PINGGY_TOKEN))
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
        links, ready, _, _ = read_state()
        if links and ready:
            ok = alive_links(links)
            if ok:
                status.success("♻️ အရင် link သုံးလို့ရသေးတယ် — အသစ်မထုတ်ပါ")
                show_links(links, ok)
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
        links, ready, error, start_t = read_state()
        fresh = start_t > 0 and start_t >= fresh_after

        if fresh and error:
            status.error(f"❌ Kaggle မှာ error: {error}")
            return

        if fresh and links and not ready:
            status.info(f"⏳ Tunnel {len(links)} ခု ရပါပြီ၊ App စတက်နေတယ်... (၁–၃ မိနစ်)")

        if fresh and ready and links:
            ok = alive_links(links)
            if ok:
                status.success(f"✅ App အဆင်သင့်ဖြစ်ပါပြီ! ({len(ok)}/{len(links)} link စစ်ပြီး)")
                show_links(links, ok)
                return
            ready_polls += 1
            status.info("⏳ App တက်ပြီ၊ Link ချိတ်ဆက်မှု စစ်နေတယ်...")
            if ready_polls >= 15:
                status.warning("⚠️ Streamlit ကနေ စစ်လို့မရပေမဲ့ link တွေကို ကိုယ်တိုင် စမ်းကြည့်ပါ")
                show_links(links)
                return
        time.sleep(2)

    status.warning("မအောင်မြင်သေးပါ။ Kaggle → Your Work → Logs ကို စစ်ကြည့်ပါ။")


# ------------------------------------------------------------ UI
if st.button("🚀 Link ယူမယ် (ရှိပြီးသား သုံးလို့ရရင် ပြန်သုံးမယ်)"):
    run(False)

if st.button("🔄 အသစ်အတင်းထုတ်မယ်"):
    run(True)
