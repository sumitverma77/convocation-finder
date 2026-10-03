import pandas as pd
import streamlit as st
from rapidfuzz import fuzz, process

from pipeline.config import CANDIDATES_CSV, RESULTS_CSV, VIDEO_ID

st.set_page_config(page_title="Find Your Convocation Moment", page_icon="🎓", layout="centered")

# Small, phone-first styling: roomy tap targets, rounded cards, no horizontal overflow.
st.markdown(
    """
    <style>
      .block-container {padding: 3.2rem 1rem 3rem; max-width: 720px;}
      .hero {background: linear-gradient(135deg,#4f46e5,#7c3aed 60%,#db2777); color:#fff; border-radius:18px;
             padding:1.1rem 1.2rem; margin-bottom:1rem; text-align:center;}
      .hero h1 {font-size:1.45rem; margin:0 0 .25rem; line-height:1.25; color:#fff;}
      .hero p {margin:0; opacity:.92; font-size:.95rem;}
      .card {border:1px solid rgba(128,128,128,.25); border-radius:14px; padding:.8rem 1rem; margin:.6rem 0;}
      .badge {display:inline-block; padding:.15rem .6rem; border-radius:999px; font-weight:600; font-size:.85rem;}
      .b-high {background:#dcfce7; color:#166534;} .b-mid {background:#fef9c3; color:#854d0e;}
      .b-low {background:#fee2e2; color:#991b1b;}
      .stTextInput input, .stSelectbox div[data-baseweb="select"] {font-size:1rem; min-height:48px;}
      .stTabs [data-baseweb="tab-list"] {overflow-x:auto; gap:.25rem;}
      iframe, video {max-width:100%;}
      a {word-break:break-word;}
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data
def load_data():
    res = pd.read_csv(RESULTS_CSV)
    cand = pd.read_csv(CANDIDATES_CSV)
    # same name twice -> add "#n" so people can tell the entries apart (no other personal detail is shown)
    dup = res.groupby("name").cumcount() + 1
    multi = res.groupby("name")["name"].transform("size") > 1
    res["label"] = res["name"].where(~multi, res["name"] + "  ·  #" + dup.astype(str))
    return res, cand


def hms(t):
    t = int(t)
    return f"{t // 3600}:{t % 3600 // 60:02d}:{t % 60:02d}"


def badge(conf):
    conf = int(conf)
    cls = "b-high" if conf >= 90 else "b-mid" if conf >= 80 else "b-low"
    return f'<span class="badge {cls}">{conf}% sure</span>'


def share_link(name, seconds):
    from urllib.parse import quote
    url = f"https://youtu.be/{VIDEO_ID}?t={int(seconds)}"
    text = f"Look, this is the moment {name.title()} got the degree at the convocation! 🎓 {url}"
    return f"https://wa.me/?text={quote(text)}"


def show_moment(c, title=None, name=None):
    if title:
        st.markdown(f"**{title}**")
    st.markdown(
        f'<div class="card">{badge(c["confidence"])} &nbsp; ⏱️ <b>{c["timestamp"]}</b>'
        + (" &nbsp; ✅ fits your slot" if c.get("in_window") else "") + "</div>",
        unsafe_allow_html=True,
    )
    st.caption(f"What the speech recognition heard here: “{c['heard']}” (source: {c['sources']})"
               if "sources" in c and pd.notna(c.get("sources")) else f"Heard: “{c['heard']}”")
    st.video(f"https://www.youtube.com/watch?v={VIDEO_ID}", start_time=int(c["seconds"]))
    links = f"[▶️ Open on YouTube](https://youtu.be/{VIDEO_ID}?t={int(c['seconds'])})"
    if name:
        links += f" &nbsp;&nbsp; [📲 Share on WhatsApp]({share_link(name, c['seconds'])})"
    st.markdown(links)


res, cand = load_data()

st.markdown(
    '<div class="hero"><h1>🎓 Find Your Convocation Moment</h1>'
    "<p>Type your name and jump to the second you crossed the stage.</p></div>",
    unsafe_allow_html=True,
)
st.caption("Names were read out live and transcribed by software, so we always show how sure we are.")

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

        if row["status"] == "confident":
            st.success(f"Congratulations {row['name'].split()[0].title()}! 🎉 We found your moment.")
            if st.session_state.get("celebrated") != int(row["id"]):
                st.balloons()                                  # tiny bit of fun, once per student
                st.session_state["celebrated"] = int(row["id"])
            show_moment(mine.iloc[0], name=row["name"])
            if len(mine) > 1:
                with st.expander("Not you? Other possible moments"):
                    for _, c in mine.iloc[1:].iterrows():
                        show_moment(c, f"Alternative {int(c['rank'])}", name=row["name"])
                        st.write("---")

        elif row["status"] == "possible":
            st.warning(f"We are not sure. Here {'is' if len(mine) == 1 else 'are'} {len(mine)} possible "
                       f"moment{'s' if len(mine) > 1 else ''}, best guess first. "
                       "Please check which one is you.")
            tabs = st.tabs([f"Option {int(c['rank'])} · {int(c['confidence'])}%" for _, c in mine.iterrows()])
            for tab, (_, c) in zip(tabs, mine.iterrows()):
                with tab:
                    show_moment(c, name=row["name"])
            if pd.notna(row["expected_from"]) and row["expected_from"] != "":
                st.caption(f"Students seated near you were mostly called between "
                           f"{hms(row['expected_from'])} and {hms(row['expected_to'])}.")

        else:
            st.info("We could not find your name in the recording.")
            if pd.notna(row["expected_from"]) and row["expected_from"] != "":
                start = int(row["expected_from"])
                st.write(f"Students seated near you were mostly called between "
                         f"**{hms(row['expected_from'])}** and **{hms(row['expected_to'])}**. "
                         "You can scrub through that part of the video.")
                st.markdown(f"[Open the video at {hms(start)}](https://youtu.be/{VIDEO_ID}?t={start})")
                st.video(f"https://www.youtube.com/watch?v={VIDEO_ID}", start_time=start)

st.write("---")
st.caption("Built with Python, Whisper, RapidFuzz and Streamlit. Confidence = how closely the name heard matches "
           "your official name, boosted when two independent transcripts agree and the time fits where you were expected.")
