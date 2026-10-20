"""
Streamlit 前端 · 时空笔友 v3.0
================================
启动：streamlit run app.py
"""
import streamlit as st
from main_v3 import run

st.set_page_config(page_title="时空笔友", page_icon="✉️", layout="centered")

st.title("✉️ 时空笔友")
st.caption("写一句话给历史，有个人会回信。")

if "history" not in st.session_state:
    st.session_state.history = []

with st.form("letter_form"):
    user_text = st.text_area(
        "今天想写点什么？",
        placeholder="最近有点累，考研压力大，不知道自己能不能坚持……",
        height=120,
    )
    submitted = st.form_submit_button("寄出 →")

if submitted and user_text.strip():
    with st.spinner("正在穿越时空，找一位懂你的人…"):
        result = run(user_text.strip())
    st.session_state.history.append(result)

# 展示最新一封
if st.session_state.history:
    r = st.session_state.history[-1]
    st.divider()
    st.markdown(f"### 🕰️ 来自 {r['penpal']['name']} · {r['penpal']['era']}")
    st.info(f"情绪标签：{' · '.join(r['emotions'])}")
    st.write(r["reply"])
    with st.expander("看看他/她引用了哪些真实史料"):
        for i, e in enumerate(r["evidence_used"], 1):
            st.write(f"{i}. {e}")

# 历史信箱
if len(st.session_state.history) > 1:
    st.divider()
    st.markdown("### 📬 我的信箱")
    for i, old in enumerate(st.session_state.history[:-1], 1):
        with st.expander(f"#{i} 给 {old['penpal']['name']} 的信"):
            st.write(f"**我写的**：{old['user_letter']}")
            st.write(f"**他/她回的**：{old['reply']}")
