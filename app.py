import streamlit as st
import subprocess
import re
import threading
import time

st.set_page_config(page_title="Link ထုတ်စက်", page_icon="🔗")
st.title("🔗 Public Link ထုတ်စက်")

if "public_link" not in st.session_state:
    st.session_state.public_link = None
if "log" not in st.session_state:
    st.session_state.log = ""

def start_tunnel():
    # Cloudflare ကို Download ဆွဲမယ်
    subprocess.run("wget -q -O cloudflared https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64", shell=True)
    subprocess.run("chmod +x cloudflared", shell=True)
    
    # Tunnel ကို ဖွင့်မယ်
    proc = subprocess.Popen(
        ["./cloudflared", "tunnel", "--url", "http://localhost:8501"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )
    
    for line in proc.stdout:
        st.session_state.log += line # log ကို သိမ်းထားမယ်
        match = re.search(r"https://[a-z0-9\-]+\.trycloudflare\.com", line)
        if match:
            st.session_state.public_link = match.group(0)
            break

if st.button("🚀 Link ထုတ်မယ်"):
    if st.session_state.public_link is None:
        with st.spinner("Link ထုတ်နေတယ်... ခဏစောင့်ပါ (၃၀ စက္ကန့်လောက် ကြာနိုင်တယ်)"):
            thread = threading.Thread(target=start_tunnel)
            thread.start()
            
            # ၃၀ စက္ကန့်အထိ စောင့်ကြည့်မယ်
            for _ in range(30):
                if st.session_state.public_link:
                    break
                time.sleep(1)
    
    if st.session_state.public_link:
        st.success("✅ အောင်မြင်ပါတယ်!")
        st.markdown(f"🔗 **Public Link:** [{st.session_state.public_link}]({st.session_state.public_link})")
    else:
        st.warning("⚠️ Link မရသေးပါ။ အောက်မှာ Log ကို စစ်ကြည့်ပါ။")
        with st.expander("🛠️ Log ကြည့်ရန်"):
            st.text(st.session_state.log[-1000:]) # Log နောက်ဆုံးအပိုင်းကို ပြမယ်