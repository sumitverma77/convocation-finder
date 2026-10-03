import pandas as pd
import streamlit as st
from rapidfuzz import fuzz, process

from pipeline.config import CANDIDATES_CSV, RESULTS_CSV, VIDEO_ID

st.set_page_config(page_title="Find Your Convocation Moment", page_icon="🎓")


@st.cache_data
def load_data():
    res = pd.read_csv(RESULTS_CSV)
    cand = pd.read_csv(CANDIDATES_CSV)
    res["label"] = res["name"] + "  ·  " + res["branch"].fillna("")
    return res, cand


def hms(t):
    t = int(t)
    return f"{t // 3600}:{t % 3600 // 60:02d}:{t % 60:02d}"


def show_moment(c, title=None):
    if title:
        st.markdown(f"**{title}**")
    st.markdown(
        f"Name match confidence: **{int(c['confidence'])}%** &nbsp;·&nbsp; "
        f"Time in video: **{c['timestamp']}**"
        + (" &nbsp;·&nbsp; ✅ fits your branch's part of the ceremony" if c.get("in_window") else "")
    )
    st.caption(f"What the speech recognition heard here: “{c['heard']}” (source: {c['sources']})"
               if "sources" in c and pd.notna(c.get("sources")) else f"Heard: “{c['heard']}”")
    st.markdown(f"[Open on YouTube](https://youtu.be/{VIDEO_ID}?t={int(c['seconds'])})")
    st.video(f"https://www.youtube.com/watch?v={VIDEO_ID}", start_time=int(c["seconds"]))


res, cand = load_data()

st.title("🎓 Find Your Convocation Moment")
st.write("Type your name to find when you were called on stage. "
         "The names were read out and transcribed by software, so we always show how sure we are.")

query = st.text_input("Your name (as on the official list):").strip().upper()

if query:
    hits = process.extract(query, res["label"].tolist(), scorer=fuzz.WRatio, limit=8, score_cutoff=70)
    if not hits:
        st.error("No matching name found. Try your first and last name only.")
    else:
        labels = [h[0] for h in hits]
        label = st.selectbox("Select your name", labels) if len(labels) > 1 else labels[0]
        row = res[res["label"] == label].iloc[0]
        mine = cand[cand["id"] == row["id"]].sort_values("rank")
        st.subheader(row["name"])
        st.caption(f"Branch: {row['branch']}")

        if row["status"] == "confident":
            st.success(f"High confidence ({int(row['confidence'])}%): we found your moment.")
            show_moment(mine.iloc[0])
            if len(mine) > 1:
                with st.expander("Not you? Other possible moments"):
                    for _, c in mine.iloc[1:].iterrows():
                        show_moment(c, f"Alternative {int(c['rank'])}")
                        st.write("---")

        elif row["status"] == "possible":
            st.warning(f"We are not sure. Here {'is' if len(mine) == 1 else 'are'} {len(mine)} possible "
                       f"moment{'s' if len(mine) > 1 else ''}, best guess first. "
                       "Please check which one is you.")
            tabs = st.tabs([f"Option {int(c['rank'])} · {int(c['confidence'])}%" for _, c in mine.iterrows()])
            for tab, (_, c) in zip(tabs, mine.iterrows()):
                with tab:
                    show_moment(c)
            if pd.notna(row["expected_from"]) and row["expected_from"] != "":
                st.caption(f"Students of {row['branch']} were mostly called between "
                           f"{hms(row['expected_from'])} and {hms(row['expected_to'])}.")

        else:
            st.info("We could not find your name in the recording.")
            if pd.notna(row["expected_from"]) and row["expected_from"] != "":
                start = int(row["expected_from"])
                st.write(f"Students of **{row['branch']}** were mostly called between "
                         f"**{hms(row['expected_from'])}** and **{hms(row['expected_to'])}**. "
                         "You can scrub through that part of the video.")
                st.markdown(f"[Open the video at {hms(start)}](https://youtu.be/{VIDEO_ID}?t={start})")
                st.video(f"https://www.youtube.com/watch?v={VIDEO_ID}", start_time=start)

st.write("---")
st.caption("Built with Python, Whisper, RapidFuzz and Streamlit. Confidence = how closely the name heard matches "
           "your official name, boosted when two independent transcripts agree and the time fits your branch.")
