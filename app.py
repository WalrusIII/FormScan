import streamlit as st
from extract import extract_from_bytes, MAX_IMAGE_MB
from PIL import Image


st.title("FormScan — Handwritten Order Form Review")
st.write(
    "Upload a photo of a filled-in medical order form to extract its fields "
    "and review anything the system is unsure about."
)

uploaded = st.file_uploader(
    "Upload a form image",
    type=["jpg", "jpeg", "png", "webp"],   # first layer of file-type validation
)

if uploaded is not None:
    size_mb = uploaded.size / (1024 * 1024)

    if size_mb > MAX_IMAGE_MB:
        st.error(f"That image is {size_mb:.1f} MB, over the {MAX_IMAGE_MB} MB limit. "
                 "Please upload a smaller photo.")
        st.stop()

    # Verify the bytes are actually a valid image, not just a file with an
    # image extension. Pillow's verify() fails on anything that isn't real.
    try:
        Image.open(uploaded).verify()
    except Exception:
        st.error("That file doesn't appear to be a valid image. "
                 "Please upload a real JPG, PNG, or WebP.")
        st.stop()

    # verify() leaves the file stream consumed, so reset it before reuse.
    uploaded.seek(0)

    st.image(uploaded, caption=uploaded.name, width=400)
    st.write(f"**{uploaded.name}** — {size_mb * 1024:.0f} KB")
    
    if st.button("Extract fields"):
        with st.spinner("Reading the form..."):
            image_bytes = uploaded.getvalue()
            media_type = uploaded.type
            # Stash results in session_state so later re-runs (from editing)
            # don't trigger a fresh API call every time.
            st.session_state.results = extract_from_bytes(image_bytes, media_type)

# Outside the upload block: if we have results (from this run or a prior one),
# show the review UI.
if "results" in st.session_state:
    st.divider()
    st.subheader("Review extracted fields")
    st.caption("Fields marked in yellow were flagged as uncertain. "
               "Correct any value, then submit.")

    for i, field in enumerate(st.session_state.results):
        name = field["field"]
        value = field["value"]
        # test_type comes back as a list; show it as comma-joined text for editing.
        if isinstance(value, list):
            display_value = ", ".join(value)
        else:
            display_value = "" if value in (None, "") else str(value)

        if field["needs_review"]:
            # Flagged: show why, and give an editable box to correct it.
            st.markdown(f"⚠️ **{name}**")
            if field.get("note"):
                st.caption(field["note"])
        else:
            st.markdown(f"**{name}**")

        # A stable, unique key per field so edits persist across re-runs.
        st.text_input(
            label=name,
            value=display_value,
            key=f"field_{i}",
            label_visibility="collapsed",
        )
        st.divider()

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