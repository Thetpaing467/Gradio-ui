import streamlit as st
import subprocess
import re
import threading
import time

st.set_page_config(page_title="Link ထုတ်စက်", page_icon="🔗")
st.title("🔗 Public Link ထုတ်စက်")

# Link ကို သိမ်းထားဖို့
if "public_link" not in st.session_state:
    st.session_state.public_link = None

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
        match = re.search(r"https://[a-z0-9\-]+\.trycloudflare\.com", line)
        if match:
            st.session_state.public_link = match.group(0)
            break

if st.button("🚀 Link ထုတ်မယ်"):
    if st.session_state.public_link is None:
        with st.spinner("Link ထုတ်နေတယ်... ခဏစောင့်ပါ (၁၀ စက္ကန့်လောက်)"):
            # နောက်ခံမှာ run မယ်
            thread = threading.Thread(target=start_tunnel)
            thread.start()
            thread.join(timeout=15) # ၁၅ စက္ကန့် စောင့်မယ်
    
    if st.session_state.public_link:
        st.success("✅ အောင်မြင်ပါတယ်!")
        st.markdown(f"🔗 **Public Link:** [{st.session_state.public_link}]({st.session_state.public_link})")
    else:
        st.warning("⚠️ Link မရသေးပါ။ ခဏနေပြီး ပြန်စမ်းပါ။")