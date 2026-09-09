import streamlit as st
from PIL import Image

MAX_IMAGE_MB = 10

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