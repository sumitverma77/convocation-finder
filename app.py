import pandas as pd
import streamlit as st
from rapidfuzz import fuzz, process

VIDEO_ID = "iZuGjFTKXL8"

st.set_page_config(page_title="Find Your Convocation Moment", page_icon="🎓")


@st.cache_data
def load_data():
    ok = pd.read_csv("matched_timestamps.csv")
    ok["found"] = True
    try:
        review = pd.read_csv("needs_review.csv")
    except FileNotFoundError:
        review = pd.DataFrame(columns=ok.columns)
    review["found"] = False
    return pd.concat([ok, review], ignore_index=True)


df = load_data()
all_names = df["Official Name"].tolist()

st.title("🎓 Find Your Convocation Moment")
st.write("Type your name to jump to the exact moment you were called on stage.")

query = st.text_input("Your name (as on the official list):").strip().upper()

if query:
    # fuzzy search so small spelling differences still find the right person
    hits = process.extract(query, all_names, scorer=fuzz.WRatio, limit=8, score_cutoff=70)
    if not hits:
        st.error("No matching name found. Try your first and last name only.")
    else:
        options = [h[0] for h in hits]
        choice = st.selectbox("Select your name", options) if len(options) > 1 else options[0]
        row = df[df["Official Name"] == choice].iloc[0]
        st.subheader(choice)
        if row["found"]:
            start = int(row["Seconds"])
            st.write(f"Called at **{row['Timestamp']}** in the video "
                     f"(matched with {int(row['Match Confidence %'])}% confidence).")
            st.markdown(f"[Open on YouTube](https://youtu.be/{VIDEO_ID}?t={start})")
            st.video(f"https://www.youtube.com/watch?v={VIDEO_ID}", start_time=start)
            st.caption("Timing is automatic and can be off by a few seconds; scrub a little back or forward.")
        else:
            st.warning("We could not locate this name automatically yet. It is queued for manual review.")

st.write("---")
st.caption("Built with Python, Whisper, RapidFuzz and Streamlit.")
