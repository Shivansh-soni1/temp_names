from flask import Flask, render_template, request, send_file
import pandas as pd
import re
import os
import uuid
from difflib import get_close_matches

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "outputs"
ALLOWED_EXTENSIONS = {"csv", "xlsx", "xls"}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# =============================
# DICTIONARIES
# =============================

district_renames = {
    "Cuddapah": "Ysr Kadapa",
    "Allahabad": "Prayagraj",
    "Faizabad": "Ayodhya",
    "Bardhaman": "Purba Bardhaman",
    "Hugli": "Hooghly",
}

state_corrections = {
    "WESTBENGAL": "West Bengal",
    "Orissa": "Odisha",
    "andhra pradesh": "Andhra Pradesh",
    "Uttaranchal": "Uttarakhand",
}

# =============================
# HELPERS
# =============================

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def normalize(text):
    if pd.isna(text):
        return None
    text = str(text).lower().strip()
    text = re.sub(r"[^\w\s]", "", text)
    return text

district_map = {normalize(k): v for k, v in district_renames.items()}
state_map = {normalize(k): v for k, v in state_corrections.items()}

def fuzzy_correct(value, mapping, cutoff=0.85):
    if pd.isna(value):
        return value
    key = normalize(value)
    if key in mapping:
        return mapping[key]
    matches = get_close_matches(key, mapping.keys(), n=1, cutoff=cutoff)
    return mapping[matches[0]] if matches else value

# =============================
# CLEAN FILE
# =============================

def clean_file(input_path, output_path):
    # READ
    if input_path.endswith(".csv"):
        df = pd.read_csv(input_path)
    else:
        df = pd.read_excel(input_path)

    # COLUMN CHECK
    state_cols = [c for c in df.columns if "state" in c.lower()]
    district_cols = [c for c in df.columns if "district" in c.lower()]

    if not state_cols:
        raise ValueError("State column not found")
    if not district_cols:
        raise ValueError("District column not found")

    state_col = state_cols[0]
    district_col = district_cols[0]

    # CLEAN
    df[state_col] = df[state_col].apply(lambda x: fuzzy_correct(x, state_map))
    df[district_col] = df[district_col].apply(lambda x: fuzzy_correct(x, district_map))

    # WRITE SAME FORMAT
    if output_path.endswith(".csv"):
        df.to_csv(output_path, index=False)
    else:
        df.to_excel(output_path, index=False)

# =============================
# ROUTES
# =============================

@app.route("/")
def home():
    return render_template("upload.html")

@app.route("/clean", methods=["POST"])
def clean():
    if "file" not in request.files:
        return render_template("upload.html", error="❌ Please upload a file")

    file = request.files["file"]

    if file.filename == "":
        return render_template("upload.html", error="❌ No file selected")

    if not allowed_file(file.filename):
        return render_template(
            "upload.html",
            error="❌ Only CSV and Excel files are allowed"
        )

    uid = uuid.uuid4().hex
    input_path = os.path.join(UPLOAD_FOLDER, f"{uid}_{file.filename}")
    output_path = os.path.join(OUTPUT_FOLDER, f"cleaned_{uid}_{file.filename}")

    try:
        file.save(input_path)
        clean_file(input_path, output_path)
        return send_file(output_path, as_attachment=True)

    except ValueError as e:
        return render_template("upload.html", error=f"❌ {str(e)}")

    except Exception:
        return render_template(
            "upload.html",
            error="❌ Error while processing file. Check format and columns."
        )

# =============================
# RUN
# =============================

if __name__ == "__main__":
    app.run(debug=True)
