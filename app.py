import streamlit as st
import subprocess
import re
import threading
import time
import os

st.set_page_config(page_title="Link ထုတ်စက်", page_icon="🔗")
st.title("🔗 Public Link ထုတ်စက်")

PORT = 8501  # Streamlit run နေတဲ့ port

@st.cache_resource
def get_tunnel_state():
    # thread နဲ့ main နှစ်ခုလုံး မျှသုံးမယ့် state
    return {"link": None, "log": "", "started": False, "proc": None}

state = get_tunnel_state()

def start_tunnel():
    if not os.path.exists("cloudflared"):
        subprocess.run(
            "wget -q -O cloudflared https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64",
            shell=True,
        )
        subprocess.run("chmod +x cloudflared", shell=True)

    proc = subprocess.Popen(
        ["./cloudflared", "tunnel", "--url", f"http://localhost:{PORT}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    state["proc"] = proc

    for line in proc.stdout:
        state["log"] += line
        match = re.search(r"https://[a-z0-9\-]+\.trycloudflare\.com", line)
        if match and not state["link"]:
            state["link"] = match.group(0)
        # break မလုပ်ဘူး - pipe ဆက်ဖတ်နေမှ process မရပ်မှာ

if st.button("🚀 Link ထုတ်မယ်"):
    if not state["started"]:
        state["started"] = True
        threading.Thread(target=start_tunnel, daemon=True).start()

    with st.spinner("Link ထုတ်နေတယ်... ခဏစောင့်ပါ (၃၀ စက္ကန့်လောက် ကြာနိုင်တယ်)"):
        for _ in range(60):
            if state["link"]:
                break
            time.sleep(1)

if state["link"]:
    st.success("✅ အောင်မြင်ပါတယ်!")
    st.markdown(f"🔗 **Public Link:** [{state['link']}]({state['link']})")
elif state["started"]:
    st.warning("⚠️ Link မရသေးပါ။ ခဏနေရင် ထပ်နှိပ်ပါ၊ ဒါမှမဟုတ် Log ကို စစ်ကြည့်ပါ။")
    with st.expander("🛠️ Log ကြည့်ရန်"):
        st.text(state["log"][-1000:])