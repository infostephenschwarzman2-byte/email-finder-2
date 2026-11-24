import concurrent.futures as cf

import pandas as pd
import streamlit as st

from email_finder import process

st.set_page_config(page_title="Bulk Email Finder", page_icon="📧", layout="wide")
st.title("📧 Bulk Email Finder")
st.caption("Sites paste karo (ek line me ek), button dabao, emails + Facebook + LinkedIn mil jayenge.")

text = st.text_area("Sites list", height=220, placeholder="example.com\nanothersite.co.uk\nmagazine.com")

if st.button("Find Emails", type="primary"):
    sites = list(dict.fromkeys(l.strip() for l in text.splitlines() if l.strip()))
    if not sites:
        st.warning("Pehle kuch sites paste karo.")
    else:
        bar = st.progress(0.0, text="Check ho rahi hain...")
        rows = []
        with cf.ThreadPoolExecutor(max_workers=10) as ex:
            futures = [ex.submit(process, s) for s in sites]
            for i, fut in enumerate(cf.as_completed(futures), 1):
                rows.append(fut.result())
                bar.progress(i / len(sites), text=f"{i}/{len(sites)} done")
        order = {s: i for i, s in enumerate(sites)}
        rows.sort(key=lambda r: order.get(r["site"], 0))
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True)
        st.download_button(
            "Download CSV",
            df.to_csv(index=False).encode("utf-8-sig"),
            "results.csv",
            "text/csv",
        )
