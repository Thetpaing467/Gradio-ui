import streamlit as st
import os
import re
import time
from kaggle.api.kaggle_api_extended import KaggleApi

st.set_page_config(page_title="Kaggle Link ထုတ်စက်", page_icon="🔗")
st.title("🔗 Kaggle Link ထုတ်စက်")

# ⚠️ ဒီနေရာမှာ ခင်ဗျားရဲ့ Kaggle Username နဲ့ Key ကို ထည့်ပါ
os.environ['KAGGLE_USERNAME'] = "thetuaiiaa"
os.environ['KAGGLE_KEY'] = "e949c9ede1ed6d03eda8811b5421a262"

KERNEL_NAME = "thetuaiiaa/notebook720a308f75"

if st.button("🚀 စတင်မယ် (Link ထုတ်မယ်)"):
    with st.spinner("Kaggle မှာ Run နေတယ်... ခဏစောင့်ပါ (စက္ကန့် ၃၀-၆၀ လောက် ကြာနိုင်တယ်)"):
        try:
            # 1. Kaggle API ကို ချိတ်ဆက်မယ်
            api = KaggleApi()
            api.authenticate()
            
            # 2. Kaggle ကို Run ခိုင်းမယ်
            api.kernels_push(KERNEL_NAME)
            st.info("✅ Kaggle က Run ပြီးပါပြီ။ Link ကို စောင့်နေတယ်...")
            
            time.sleep(25) # Link ထွက်လာအောင် စောင့်မယ်
            
            # 3. Output (Log) ကို ဆွဲထုတ်ပြီး Link ရှာမယ်
            api.kernels_output(KERNEL_NAME, path="./output")
            
            link = None
            if os.path.exists("./output"):
                for f in os.listdir("./output"):
                    try:
                        with open(os.path.join("./output", f), "r", errors="ignore") as file:
                            content = file.read()
                            match = re.search(r"https://[a-zA-Z0-9\-]+\.trycloudflare\.com", content)
                            if match:
                                link = match.group(0)
                                break
                    except:
                        pass
            
            if link:
                st.success("✅ အောင်မြင်ပါတယ်!")
                st.markdown(f"🔗 **Public Link:** [{link}]({link})")
            else:
                st.warning("⚠️ Link မတွေ့ပါ။ Kaggle က မထုတ်ပေးသေးဘူး ဖြစ်နိုင်ပါတယ်။ (ခဏနေပြီး ပြန်စမ်းပါ)")
                
        except Exception as e:
            st.error(f"Error: {e}")