import streamlit as st
import google.generativeai as genai
import os
from datetime import datetime
import json
import pandas as pd
import glob
from openpyxl import Workbook

# -----------------------------
# NEW: API CONFIG (Modern Model)
# -----------------------------
genai.configure(api_key=os.getenv("GEMINI_API"))

model = genai.GenerativeModel("models/gemini-2.5-flash")


# -----------------------------
# Helper Functions
# -----------------------------

def generate_quiz(full_content: str):
    prompt = f"""
    Create a cybersecurity quiz with EXACTLY 10 MCQs.

    STRICT JSON FORMAT:
    {{
        "quiz": [
            {{
                "question": "...",
                "options": ["A. ...", "B. ...", "C. ...", "D. ..."],
                "correct": "A",
                "explanation": "..."
            }}
        ]
    }}

    No extra text. No notes. No paragraphs.

    Content to use:
    {full_content}
    """

    response = model.generate_content(prompt)
    return response.text.strip()


def parse_quiz(quiz_text: str):
    data = json.loads(quiz_text)
    parsed = []
    for item in data["quiz"]:
        parsed.append({
            "question": item["question"],
            "options": item["options"],
            "correct": item["correct"],
            "explanation": item["explanation"]
        })
    return parsed


def save_quiz_file(quiz_text, start_time, end_time):
    with open("latest_quiz.json", "w") as f:
        json.dump({
            "quiz_text": quiz_text,
            "start_time": start_time,
            "end_time": end_time
        }, f, indent=4)


def load_quiz_file():
    try:
        with open("latest_quiz.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return None


def save_student_results(student_name, score, parsed_questions, user_answers):
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    results = []
    for i, q in enumerate(parsed_questions):
        results.append({
            "question": q["question"],
            "student_answer": user_answers[i],
            "correct_answer": q["correct"],
            "explanation": q["explanation"]
        })
    filename = f"results_{student_name}_{timestamp}.json"
    with open(filename, "w") as f:
        json.dump({
            "student_name": student_name,
            "score": score,
            "answers": results
        }, f, indent=4)
    return filename


def load_all_results():
    all_results = []
    for file in glob.glob("results_*.json"):
        with open(file, "r") as f:
            all_results.append(json.load(f))
    return all_results


def export_excel(results):
    df = pd.DataFrame([{
        "Student": r["student_name"],
        "Score": r["score"]
    } for r in results])

    df.to_excel("marks_sheet.xlsx", index=False)
    return "marks_sheet.xlsx"


# --------------------------------------------------
# STREAMLIT APP UI
# --------------------------------------------------

st.title("Cybersecurity Quiz Platform")
mode = st.sidebar.selectbox("Select Mode:", ["Teacher", "Student"])

# --------------------------------------------------
# TEACHER MODE (PASSWORD PROTECTED)
# --------------------------------------------------

if mode == "Teacher":
    st.header("Teacher Login")

    password = st.text_input("Enter Teacher Password:", type="password")
    if password != "admin123":  # change this password
        st.warning("Enter correct password to continue.")
        st.stop()

    st.success("Login successful ✔")
    st.header("Teacher Dashboard")

    # -----------------------------------
    # NEW: Mandatory + Optional Content
    # -----------------------------------

    st.subheader("Quiz Information")

    mandatory_topic = st.text_input("Enter Main Quiz Topic (Required)*")

    optional_text = st.text_area("Optional Supporting Content (Not Required)")

    optional_file = st.file_uploader(
        "Upload Optional Document (PDF, TXT, DOCX)", 
        type=["pdf", "txt", "docx"]
    )

    optional_file_text = ""

    # File Reading Logic
    if optional_file:
        try:
            if optional_file.type == "text/plain":
                optional_file_text = optional_file.read().decode("utf-8")

            elif optional_file.type == "application/pdf":
                import PyPDF2
                reader = PyPDF2.PdfReader(optional_file)
                text = ""
                for page in reader.pages:
                    text += page.extract_text()
                optional_file_text = text

            elif optional_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                import docx
                doc = docx.Document(optional_file)
                text = "\n".join([p.text for p in doc.paragraphs])
                optional_file_text = text

        except:
            st.warning("Unable to read uploaded file.")

    # Quiz Time
    start_time = st.datetime_input("Select Quiz Start Date & Time")
    end_time = st.datetime_input("Select Quiz Expiry Date & Time")

    # Generate Quiz Button
    if st.button("Generate Quiz"):
        if not mandatory_topic.strip():
            st.error("Main Quiz Topic is required!")
        else:
            full_content = (
                f"MAIN TOPIC:\n{mandatory_topic}\n\n"
                f"OPTIONAL TEXT:\n{optional_text}\n\n"
                f"OPTIONAL FILE CONTENT:\n{optional_file_text}"
            )

            with st.spinner("Generating quiz using Gemini..."):
                try:
                    quiz_text = generate_quiz(full_content)
                    save_quiz_file(quiz_text, str(start_time), str(end_time))

                    st.success("🎉 Quiz generated successfully!")

                    parsed = parse_quiz(quiz_text)
                    st.subheader("Preview of First 3 Questions:")
                    for q in parsed[:3]:
                        st.write(q["question"])
                        st.write(q["options"])

                except Exception as e:
                    st.error(f"Error: {e}")

    # Students Results Section
    st.subheader("All Student Results")
    results = load_all_results()

    if results:
        df = pd.DataFrame([{
            "Student": r["student_name"],
            "Score": r["score"]
        } for r in results])
        st.table(df)

        if st.button("Download Marks Sheet (Excel)"):
            filename = export_excel(results)
            with open(filename, "rb") as f:
                st.download_button("Download Excel File", f, filename)
    else:
        st.info("No student results available yet.")


# --------------------------------------------------
# STUDENT MODE
# --------------------------------------------------

elif mode == "Student":
    st.header("Take Quiz")

    student_name = st.text_input("Enter your name:").strip().replace(" ", "_") or "Unknown"

    quiz_data = load_quiz_file()

    if not quiz_data:
        st.warning("Quiz not created yet.")
        st.stop()

    quiz_text = quiz_data["quiz_text"]
    start_time = datetime.fromisoformat(quiz_data["start_time"])
    end_time = datetime.fromisoformat(quiz_data["end_time"])
    now = datetime.now()

    # Prevent early/late access
    if now < start_time:
        st.error(f"Quiz will start at: {start_time}")
        st.stop()

    if now > end_time:
        st.error(f"Quiz expired at: {end_time}")
        st.stop()

    parsed_questions = parse_quiz(quiz_text)

    user_answers = []

    for i, q in enumerate(parsed_questions):
        st.subheader(f"Q{i+1}: {q['question']}")
        answer = st.radio("Choose your answer:", q["options"], key=f"q{i}", index=None)
        user_answers.append(answer)

    if st.button("Submit Answers"):
        if None in user_answers:
            st.error("Answer all questions before submitting.")
            st.stop()

        score = 0
        for i, q in enumerate(parsed_questions):
            selected_letter = user_answers[i][0]
            if selected_letter == q["correct"]:
                score += 1

        st.success(f"{student_name}, you scored {score} / {len(parsed_questions)}")

        filename = save_student_results(student_name, score, parsed_questions, user_answers)
        st.info(f"Saved as: **{filename}**")
