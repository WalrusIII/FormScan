import streamlit as st
import json
from extract import extract_from_bytes, MAX_IMAGE_MB
from PIL import Image

st.set_page_config(layout="wide", page_title="FormScan")

st.markdown("""
<style>
    /* App title in Loyal Blue */
    h1 { color: #124075; }
    /* Section subheaders in Bright Blue */
    h2, h3 { color: #0066FF; }
    /* Primary buttons: Loyal Blue background */
    .stButton > button {
        background-color: #124075;
        color: white;
        border: none;
    }
    .stButton > button:hover {
        background-color: #0066FF;
        color: white;
    }
</style>
""", unsafe_allow_html=True)

def blank_form_download(key):
    """Render a download button for the blank form. `key` must be unique
    per placement, since Streamlit requires unique keys for repeated widgets."""
    with open("blank_test_medical_order_form.pdf", "rb") as f:
        st.download_button(
            label="📄 Download a blank form to try",
            data=f.read(),
            file_name="medical_order_form.pdf",
            mime="application/pdf",
            key=key,
        )

def render_footer():
    st.divider()
    st.caption("FormScan AI · Built by [Grady Walworth](https://github.com/WalrusIII) · 2026")

st.title("FormScan — Handwritten Order Form Review")

# --- Landing: choose demo or live mode (stored so re-runs don't reset it) ---
if "mode" not in st.session_state:
    st.session_state.mode = None

if st.session_state.mode is None:
    st.write(
        "Upload a photo of a handwritten medical order form to extract its "
        "fields and review anything the system is unsure about."
    )
    col1, col2 = st.columns(2)
    with col1:
        if st.button("👀 See a demo", use_container_width=True):
            st.session_state.mode = "demo"
            st.rerun()
        st.caption("Instant sample — no upload, no cost.")
    with col2:
        if st.button("🔑 Try it live", use_container_width=True):
            st.session_state.mode = "live"
            st.rerun()
        st.caption("Upload your own form (requires password).")
    st.divider()
    st.caption(
        "**Want to try it with your own handwriting?** Download the blank form, "
        "print and fill it out, snap a photo, then use **Try it live** to upload it."
    )
    blank_form_download("dl_landing")
    render_footer()
    st.stop()   # nothing else renders until a mode is chosen

# --- A small "start over" control, available in either mode ---
if st.button("← Start over"):
    st.session_state.clear()
    st.rerun()

# --- DEMO MODE: load the saved sample result, no API call ---
if st.session_state.mode == "demo":
    if "results" not in st.session_state:
        with open("sample_result.json") as f:
            st.session_state.results = json.load(f)
        with open("test_order_form2.jpg", "rb") as f:
            st.session_state.form_image = f.read()
    st.info("Demo mode — showing a pre-computed sample. No data is uploaded or sent.")

# --- LIVE MODE: password gate, then the upload flow ---
if st.session_state.mode == "live":
    if not st.session_state.get("authed", False):
        pw = st.text_input("Enter password to run live extraction", type="password")
        if pw:
            if pw == st.secrets.get("APP_PASSWORD", ""):
                st.session_state.authed = True
                st.rerun()
            else:
                st.error("Incorrect password.")
        st.stop()   # block the rest until authenticated


    # --- authenticated live upload flow (your existing upload block) ---
    uploaded = st.file_uploader(
        "Upload a form image",
        type=["jpg", "jpeg", "png", "webp"],
    )
    # Offer the blank form so people can print, fill, and try it themselves.
    blank_form_download("dl_live")

    if uploaded is not None:
        size_mb = uploaded.size / (1024 * 1024)
        if size_mb > MAX_IMAGE_MB:
            st.error(f"That image is {size_mb:.1f} MB, over the {MAX_IMAGE_MB} MB limit.")
            st.stop()
        try:
            Image.open(uploaded).verify()
        except Exception:
            st.error("That file doesn't appear to be a valid image.")
            st.stop()
        uploaded.seek(0)

        st.image(uploaded, caption=uploaded.name, width=400)
        if st.button("Extract fields"):
            with st.spinner("Reading the form..."):
                st.session_state.results = extract_from_bytes(uploaded.getvalue(), uploaded.type)
                st.session_state.form_image = uploaded.getvalue()


# Outside the upload block: if we have results (from this run or a prior one),
# show the review UI.
if "results" in st.session_state:
    st.divider()
    st.subheader("Review extracted fields")

    col_form, col_fields = st.columns([1.3, 1], gap="large")

    with col_form:
        # Fixed-height container -> the form stays put and scrolls on its own,
        # so it doesn't disappear as you work down the fields on the right.
        with st.container(height=800):
            st.image(st.session_state.form_image, use_container_width=True)

    with col_fields:
        with st.container(height=800):
            st.caption("🟡 medium confidence · 🔴 low confidence · verify against the form.")
            for i, field in enumerate(st.session_state.results):
                with st.container(border=True):
                    name = field["field"]
                    value = field["value"]
                    display_value = ", ".join(value) if isinstance(value, list) else (
                        "" if value in (None, "") else str(value))

                    conf = field.get("confidence", "high")
                    if field["needs_review"]:
                        icon = "🔴" if conf == "low" else "🟡"
                        st.markdown(f"{icon} **{name}**")
                    else:
                        st.markdown(f"**{name}**")
                    if field["needs_review"] and field.get("note"):
                        st.caption(field["note"])

                    st.text_input(name, value=display_value, key=f"field_{i}",
                                label_visibility="collapsed")

    if st.button("Confirm & save"):
        corrected = []
        for i, field in enumerate(st.session_state.results):
            # Read the human's final value for this field out of session state,
            # using the same key we gave the widget.
            final_value = st.session_state[f"field_{i}"]
            # Record whether the human changed the model's original reading.
            original = field["value"]
            original_str = ", ".join(original) if isinstance(original, list) else (
                "" if original in (None, "") else str(original))

            corrected.append({
                "field": field["field"],
                "final_value": final_value,
                "was_flagged": field["needs_review"],
                "was_corrected": final_value != original_str,
            })

        st.session_state.corrected = corrected
        st.success("Saved.")

# Show the confirmed result (persists across re-runs, like results does).
if "corrected" in st.session_state:
    st.divider()
    st.subheader("Confirmed data")
    corrected = st.session_state.corrected

    changed = [c for c in corrected if c["was_corrected"]]
    st.write(f"{len(corrected)} fields confirmed — "
             f"{len(changed)} corrected by reviewer.")
    st.json(corrected)

st.divider()
render_footer()