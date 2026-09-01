from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor

W, H = letter          # 612 x 792
xL = 50
xR = W - 50            # 562
FULL = xR - xL         # 512

navy   = HexColor("#1f3a5f")
gray   = HexColor("#444444")
line   = HexColor("#000000")
light  = HexColor("#999999")

BOXH = 26              # write-in box height (roomy for handwriting)

c = canvas.Canvas("/home/claude/medical_order_form.pdf", pagesize=letter)

def box(x, top, w, h=BOXH):
    """Draw a write-in box whose TOP edge is at y=top."""
    c.setStrokeColor(line); c.setLineWidth(1.2)
    c.rect(x, top - h, w, h)

def flabel(x, y, text, size=9.5):
    c.setFillColor(navy); c.setFont("Helvetica-Bold", size)
    c.drawString(x, y, text)

def sub(x, y, text):
    c.setFillColor(gray); c.setFont("Helvetica", 7.5)
    c.drawString(x, y, text)

def checkbox(x, y, text):
    c.setStrokeColor(line); c.setLineWidth(0.9)
    c.rect(x, y - 9, 9, 9)
    c.setFillColor(HexColor("#000000")); c.setFont("Helvetica", 9)
    c.drawString(x + 14, y - 8, text)

def radio(x, y, text):
    c.setStrokeColor(line); c.setLineWidth(0.9)
    c.circle(x + 4.5, y - 4.5, 4.7, stroke=1, fill=0)
    c.setFillColor(HexColor("#000000")); c.setFont("Helvetica", 9)
    c.drawString(x + 14, y - 8, text)

def section(y, text):
    c.setFillColor(navy); c.setFont("Helvetica-Bold", 11.5)
    c.drawString(xL, y, text)
    c.setStrokeColor(light); c.setLineWidth(0.6)
    c.line(xL, y - 5, xR, y - 5)
    return y - 20

# ---------- Header ----------
y = H - 46
c.setFillColor(navy); c.setFont("Helvetica-Bold", 11)
c.drawString(xL, y, "ABC HEALTH")
c.setFillColor(gray); c.setFont("Helvetica", 8.5)
c.drawString(xL, y - 11, "MEDICAL SUPPLIES")
c.setFillColor(navy); c.setFont("Helvetica-Bold", 21)
c.drawCentredString(W / 2 + 40, y - 4, "Medical Order Form")
y -= 28
c.setStrokeColor(navy); c.setLineWidth(1.3)
c.line(xL, y, xR, y)
y -= 20

# ---------- Patient Information ----------
y = section(y, "PATIENT INFORMATION")

# Patient Name (3 wide boxes)
flabel(xL, y, "Patient Name")
y -= 13
w1 = FULL * 0.36; w2 = FULL * 0.26; w3 = FULL * 0.36
g = 6
box(xL, y, w1)
box(xL + w1 + g, y, w2 - g)
box(xL + w1 + w2 + g, y, w3 - g)
sub(xL, y - BOXH - 9, "First Name")
sub(xL + w1 + g, y - BOXH - 9, "Middle Name")
sub(xL + w1 + w2 + g, y - BOXH - 9, "Last Name")
y -= (BOXH + 22)

# Row: DOB (left) + Gender (right)
flabel(xL, y, "Date of Birth")
flabel(xL + FULL * 0.55, y, "Gender")
y -= 13
dobw = 52
box(xL, y, dobw)
box(xL + dobw + g, y, dobw)
box(xL + 2 * (dobw + g), y, dobw + 14)
sub(xL, y - BOXH - 9, "Month")
sub(xL + dobw + g, y - BOXH - 9, "Day")
sub(xL + 2 * (dobw + g), y - BOXH - 9, "Year")
# gender radios on same line as the boxes
radio(xL + FULL * 0.55, y - 6, "Male")
radio(xL + FULL * 0.55 + 70, y - 6, "Female")
y -= (BOXH + 22)

# Row: Phone (left half) + Email (right half)
half = (FULL - 20) / 2
flabel(xL, y, "Phone Number")
flabel(xL + half + 20, y, "Email")
y -= 13
box(xL, y, half)
box(xL + half + 20, y, half)
y -= (BOXH + 16)

# ---------- Address ----------
y = section(y, "ADDRESS")
flabel(xL, y, "Street Address"); y -= 13
box(xL, y, FULL); y -= (BOXH + 6)
box(xL, y, FULL)
sub(xL, y - BOXH - 9, "Street Address Line 2")
y -= (BOXH + 20)
cw = FULL * 0.44; sw = FULL * 0.30; zw = FULL * 0.26
box(xL, y, cw - g)
box(xL + cw, y, sw - g)
box(xL + cw + sw, y, zw)
sub(xL, y - BOXH - 9, "City")
sub(xL + cw, y - BOXH - 9, "State / Province")
sub(xL + cw + sw, y - BOXH - 9, "Postal / Zip Code")
y -= (BOXH + 20)

# ---------- Order Details ----------
y = section(y, "ORDER DETAILS")
flabel(xL, y, "Test Type")
tx = xL + 90
for lbl in ["Test 1A", "Test 1B", "Test 2A", "Test 2B"]:
    checkbox(tx, y, lbl)
    tx += 108
y -= 22
flabel(xL, y, "ICD-10 Code"); y -= 13
box(xL, y, FULL); y -= (BOXH + 14)
flabel(xL, y, "Payment Method"); y -= 15
px = xL
for lbl in ["Primary Insurance", "Medicare", "Self Pay", "Other"]:
    radio(px, y, lbl)
    px += len(lbl) * 5.6 + 34
box(px - 18, y - 7, 100, 18)   # write-in box next to "Other"
y -= 34

# ---------- Provider Information ----------
y = section(y, "PROVIDER INFORMATION")
flabel(xL, y, "Provider Name"); y -= 13
box(xL, y, w1)
box(xL + w1 + g, y, w2 - g)
box(xL + w1 + w2 + g, y, w3 - g)
sub(xL, y - BOXH - 9, "First Name")
sub(xL + w1 + g, y - BOXH - 9, "Middle Name")
sub(xL + w1 + w2 + g, y - BOXH - 9, "Last Name")
y -= (BOXH + 22)
flabel(xL, y, "Provider NPI Number")
flabel(xL + half + 20, y, "Date")
y -= 13
box(xL, y, half)
box(xL + half + 20, y, half)
y -= (BOXH + 10)

# footer note
c.setFillColor(gray); c.setFont("Helvetica-Oblique", 7.5)
c.drawString(xL, 40, "Synthetic form for testing only — contains no real patient data (PHI).")

c.save()
print("saved")