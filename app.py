import io

import cv2
import numpy as np
import pandas as pd
import streamlit as st
from PIL import Image

from dust_analysis import compare_before_after, dust_map
from simulator import DustSurfaceSim
from wave_optimizer import AdaptiveController, find_resonance, recommend_pattern

st.set_page_config(page_title="DUSTWAVE", page_icon="〰️", layout="wide")
st.title("〰️ DUSTWAVE")
st.caption("Closed-loop, AI-adapted vibration planning for dust removal - research prototype")
st.warning("The simulation tab is a MODEL and does not prove real cleaning. Real results come from "
           "the Before/After tab using photos from your hardware tests.")

tab1, tab2, tab3, tab4 = st.tabs(["1. Analyze surface", "2. Frequency sweep",
                                  "3. Closed-loop simulation", "4. Before / After test"])


def load(file):
    return np.array(Image.open(file).convert("RGB"))


with tab1:
    surface = st.selectbox("Surface type", ["solar panel", "glass", "acrylic", "other"])
    up = st.file_uploader("Photo of the dusty surface", type=["png", "jpg", "jpeg"], key="a")
    if up:
        img = load(up)
        mask, score = dust_map(img)
        c1, c2 = st.columns(2)
        c1.image(img, caption="Surface")
        c2.image(mask, caption="High local-contrast areas (dust indicator)")
        st.metric("Dust indicator (relative score)", f"{score:.1f}%")
        st.caption("Only compare scores between photos taken with the same camera position and lighting.")
        st.session_state["dust_score"] = score
        st.session_state["surface"] = surface

with tab2:
    st.write("Upload the CSV printed by the ESP32 sketch (`freq_hz,response`), or use the demo sweep.")
    f = st.file_uploader("Sweep CSV", type=["csv"])
    if f:
        df = pd.read_csv(f)
    else:
        df = pd.read_csv("data/sample_sweep.csv")
        st.caption("Showing demo data (data/sample_sweep.csv).")
    st.line_chart(df.set_index("freq_hz")["response"])
    try:
        sweep = find_resonance(df["freq_hz"], df["response"])
        st.session_state["sweep"] = sweep
        a, b, c = st.columns(3)
        a.metric("Resonance", f"{sweep['resonance_hz']:.0f} Hz")
        b.metric("Peak / baseline", f"{sweep['peak_to_baseline']:.1f}x")
        c.metric("Reliable peak", "yes" if sweep["reliable"] else "no")
        st.json(recommend_pattern(st.session_state.get("surface", "solar panel"),
                                  st.session_state.get("dust_score", 10.0), sweep))
    except ValueError as e:
        st.error(str(e))

with tab3:
    st.write("Software-only demo of the control loop: sweep, find resonance, then adapt each cycle "
             "from the measured result.")
    cycles = st.slider("Cleaning cycles", 5, 60, 25)
    stick = st.slider("Dust stickiness (hidden from the controller)", 0.1, 0.9, 0.6)
    if st.button("Run simulation"):
        sim = DustSurfaceSim(stickiness=stick, seed=7)
        freqs = np.arange(30_000, 55_000, 250)
        res = find_resonance(freqs, [sim.sensor_response(x) for x in freqs])
        ctl = AdaptiveController(res["resonance_hz"], res["bandwidth_hz"], seed=1)
        rows = [{"cycle": 0, "dust_score": sim.dust_score(), "freq_hz": res["resonance_hz"], "duty": 0}]
        for i in range(1, cycles + 1):
            p = ctl.propose()
            ctl.report(sim.apply(p.freq_hz, p.duty, p.burst_ms))
            rows.append({"cycle": i, "dust_score": sim.dust_score(),
                         "freq_hz": p.freq_hz, "duty": p.duty})
        out = pd.DataFrame(rows)
        st.line_chart(out.set_index("cycle")["dust_score"])
        st.metric("Dust removed in simulation",
                  f"{(1 - out.dust_score.iloc[-1] / out.dust_score.iloc[0]) * 100:.0f}%")
        st.caption(f"Found resonance {res['resonance_hz']:.0f} Hz (true hidden value {sim.resonance:.0f} Hz).")
        st.dataframe(out)

with tab4:
    st.write("Upload photos from a real bench test (same camera position and lighting).")
    c1, c2 = st.columns(2)
    b = c1.file_uploader("BEFORE", type=["png", "jpg", "jpeg"], key="b")
    a = c2.file_uploader("AFTER", type=["png", "jpg", "jpeg"], key="af")
    if b and a:
        r = compare_before_after(load(b), load(a))
        m1, m2, m3 = st.columns(3)
        m1.metric("Dust score before", f"{r['score_before']:.1f}%")
        m2.metric("Dust score after", f"{r['score_after']:.1f}%")
        m3.metric("Cleaning efficiency", f"{r['cleaning_efficiency_pct']:.0f}%")
        st.image(cv2.applyColorMap(cv2.convertScaleAbs(r["change_map"], alpha=4), cv2.COLORMAP_INFERNO)[:, :, ::-1],
                 caption="Change map (bright = changed between photos)")
