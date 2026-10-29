# ===== Kaggle All-in-One (FAST): Gradio UI + Cloudflare public link =====
import os, re, sys, time, subprocess, threading, urllib.request
from importlib import metadata

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


# 0) အရင် run ထားတဲ့ app / tunnel ရှိရင် ပိတ်
sh("pkill -f 'cloudflared tunnel' ; pkill -f 'python.*app.py'")
time.sleep(1)

# ---------------------------------------------------------------- background tasks
RES = {}


def task_git():
    if os.path.exists(REPO_DIR):
        rc, out = sh(f"cd {REPO_DIR} && git fetch -q origin && git reset -q --hard origin/HEAD")
    else:
        rc, out = sh(f"git clone -q --depth 1 {REPO_URL} {REPO_DIR}")
    RES["git"] = (rc, out)
    say("git ✅" if rc == 0 else f"git ❌ {out[-300:]}")


def task_pip():
    need = {  # import/dist name -> pip spec
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
                missing.append(spec)       # version 6 ဖြစ်နေရင် 5 ပြန်ချ
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
        if rc != 0:  # package list စာရင်းဟောင်းဆိုရင်ပဲ update လုပ်
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


# tunnel ကို app မတက်ခင်ကတည်းက စတင် (link ရတာ ပိုမြန်)
url_ready = threading.Event()
tunnel_url = {}


def task_tunnel():
    t_cf.join()
    if not RES.get("cf"):
        return
    tun = subprocess.Popen([CF, "tunnel", "--url", f"http://localhost:{PORT}", "--no-autoupdate"],
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    RES["tun"] = tun
    for line in tun.stdout:              # pipe မပြည့်အောင် ဆက်ဖတ်
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

# app စတက်ဖို့ git + pip ပဲ လိုတယ် (apt က နောက်ကွယ်မှာ ဆက်လုပ်နေလို့ရ)
t_git.join()
t_pip.join()
assert RES.get("git", (1,))[0] == 0, "git clone/update မအောင်မြင်ပါ"
os.chdir(REPO_DIR)
print("Repo files:", sorted(os.listdir(".")))
assert os.path.exists(APP_FILE), "app.py repo ထဲမှာ ရှိရမယ်"

# Font (repo ထဲက font — မြန်မာစာအတွက်ပဲ သုံးမယ်)
fonts = [f for f in os.listdir(".") if f.lower().endswith((".ttf", ".otf", ".ttc"))]
if fonts:
    os.environ["RECAP_FONT"] = os.path.abspath(
        "MyanmarPadaung.ttf" if "MyanmarPadaung.ttf" in fonts else sorted(fonts)[0])
    print("Font:", os.environ["RECAP_FONT"])
os.environ["GRADIO_ANALYTICS_ENABLED"] = "False"
# os.environ["HF_TOKEN"] = "hf_xxx"
# os.environ["EDGE_TTS_PROXY"] = ""
# os.environ["YT_COOKIES"] = "/kaggle/working/cookies.txt"

# Start Gradio
env = dict(os.environ, PORT=str(PORT))
app_proc = subprocess.Popen([sys.executable, "-u", APP_FILE],
                            stdout=open(LOG, "w"), stderr=subprocess.STDOUT, env=env)
say("app စတင်နေတယ်...")

started = False
for _ in range(360):                     # 0.5s × 360 = 180s
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
    raise SystemExit("App မတက်လို့ ရပ်လိုက်တယ်။ အပေါ်က log ကို ပို့ပါ။")

# Link ပြ (app + tunnel နှစ်ခုလုံးအဆင်သင့်ဖြစ်မှ)
if url_ready.wait(timeout=60):
    print("\n🌐 PUBLIC LINK:", tunnel_url["u"], "\n", flush=True)
else:
    print("⚠️ Tunnel link မရသေးဘူး — cell ကို ပြန် run ကြည့်ပါ")

if t_apt.is_alive():
    print("ℹ️ ffmpeg / font install နောက်ကွယ်မှာ ဆက်လုပ်နေတယ် — '✅ apt' ပေါ်ပြီးမှ "
          "Video ဆွဲ / render လုပ်ပါ")

print(f"Running... (ရပ်ချင်ရင် Stop ခလုတ်နှိပ်ပါ)  log: {LOG}")
while True:
    time.sleep(30)
    if app_proc.poll() is not None:
        print(f"❌ App ရပ်သွားပြီ (exit {app_proc.returncode}) — log:\n")
        print(tail_log())
        break
