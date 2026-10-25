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

TEMPLATE = r'''
import subprocess, re, time, os, requests

TOPIC = "__TOPIC__"
PORT = __PORT__
CMD = __CMD__

open("run.sh", "w").write(CMD)
subprocess.Popen(["bash", "run.sh"])
time.sleep(__WAIT__)

os.system("wget -q -O cloudflared https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 && chmod +x cloudflared")
p = subprocess.Popen(
    ["./cloudflared", "tunnel", "--url", f"http://localhost:{PORT}"],
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
)
sent = False
for line in p.stdout:
    print(line, end="")
    m = re.search(r"https://[a-z0-9\-]+\.trycloudflare\.com", line)
    if m and not sent:
        requests.post(f"https://ntfy.sh/{TOPIC}", data=m.group(0).encode())
        sent = True
'''

slug = st.text_input("Kernel နာမည် (အင်္ဂလိပ်စာလုံး၊ ဂဏန်း၊ - သာ)", "my-link-runner")
port = st.number_input("သင့် app run မယ့် Port", value=7860)
wait = st.number_input("Server စတင်ဖို့ စောင့်မယ့် စက္ကန့်", value=60)
gpu = st.checkbox("GPU ဖွင့်မယ်", value=False)
cmd = st.text_area(
    "Kaggle ထဲမှာ run မယ့် command များ (bash)",
    "pip install -q gradio\npython -m http.server 7860 &",
    height=150,
)

if st.button("🚀 Kaggle မှာ run ပြီး Link ယူမယ်"):
    topic = "kg-" + uuid.uuid4().hex[:12]

    code = (TEMPLATE.replace("__TOPIC__", topic)
                    .replace("__PORT__", str(int(port)))
                    .replace("__CMD__", json.dumps(cmd))
                    .replace("__WAIT__", str(int(wait))))

    folder = tempfile.mkdtemp()
    with open(os.path.join(folder, "script.py"), "w") as f:
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
        res = api.kernels_push(folder)
        st.info("Kaggle ဆီ push ပြီးပါပြီ၊ run နေပါပြီ...")
        st.caption(str(res))
    except Exception as e:
        st.error(f"Push မအောင်မြင်ပါ: {e}")
        st.stop()

    link = None
    with st.spinner("Link စောင့်နေတယ်... (၁–၅ မိနစ်ကြာနိုင်)"):
        for _ in range(60):
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
    else:
        st.warning("Link မရသေးပါ။ Kaggle → Your Work → Notebook ရဲ့ Logs ကို စစ်ကြည့်ပါ။")