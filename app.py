import streamlit as st
import google.generativeai as genai
import os
from datetime import datetime
import json
import pandas as pd
import glob
from openpyxl import Workbook

# -------------------------------------------------------------
# GLOBAL ERROR-SAFE WRAPPER
# -------------------------------------------------------------
def safe_run(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except Exception:
        # Show friendly popup (no traceback)
        st.error("⚠ Something went wrong. Please try again.")
        return None


# -------------------------------------------------------------
# GEMINI API SETUP
# -------------------------------------------------------------
genai.configure(api_key=os.getenv("GEMINI_API"))
model = genai.GenerativeModel("models/gemini-2.5-flash")


# -------------------------------------------------------------
# Function: Generate Quiz (SAFE JSON)
# -------------------------------------------------------------
def generate_quiz(full_content):
    prompt = f"""
You are an expert exam generator.

Generate a quiz in STRICT JSON ONLY.
DO NOT add any explanation, markdown, comments, or extra text.

Format EXACTLY like this:
{{
  "questions": [
    {{
      "question": "string",
      "options": ["A: ...", "B: ...", "C: ...", "D: ..."],
      "correct": "A",
      "explanation": "string"
    }}
  ]
}}

Generate 10 questions based on this content:

{full_content}
"""

    response = model.generate_content(prompt)
    text = response.text.strip()

    # Remove accidental triple backticks
    if text.startswith("```"):
        text = text.replace("```json", "").replace("```", "").strip()

    return text


# -------------------------------------------------------------
# Function: Parse Quiz JSON (SAFE)
# -------------------------------------------------------------
def parse_quiz(quiz_text):
    try:
        data = json.loads(quiz_text)
    except:
        st.error("The AI did NOT return valid JSON. Please regenerate the quiz.")
        return None

    parsed = []
    for item in data["questions"]:
        parsed.append({
            "question": item["question"],
            "options": item["options"],
            "correct": item["correct"],
            "explanation": item["explanation"]
        })
    return parsed


# -------------------------------------------------------------
# Save + Load Quiz
# -------------------------------------------------------------
def save_quiz_file(quiz_text, start_time, end_time):
    try:
        with open("latest_quiz.json", "w") as f:
            json.dump({
                "quiz_text": quiz_text,
                "start_time": start_time,
                "end_time": end_time
            }, f, indent=4)
        return True
    except:
        st.error("Could not save quiz file.")
        return None


def load_quiz_file():
    try:
        with open("latest_quiz.json", "r") as f:
            return json.load(f)
    except:
        return None


# -------------------------------------------------------------
# Save student results
# -------------------------------------------------------------
def save_student_results(student_name, score, parsed_questions, user_answers):
    try:
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
    except:
        st.error("Could not save student results.")
        return None


# -------------------------------------------------------------
# Load all results
# -------------------------------------------------------------
def load_all_results():
    try:
        all_results = []
        for file in glob.glob("results_*.json"):
            with open(file, "r") as f:
                all_results.append(json.load(f))
        return all_results
    except:
        st.error("Error loading student results.")
        return []


# -------------------------------------------------------------
# Export marks sheet
# -------------------------------------------------------------
def export_excel(results):
    try:
        df = pd.DataFrame([{
            "Student": r["student_name"],
            "Score": r["score"]
        } for r in results])

        df.to_excel("marks_sheet.xlsx", index=False)
        return "marks_sheet.xlsx"
    except:
        st.error("Could not export Excel file.")
        return None


# -------------------------------------------------------------
# STREAMLIT UI
# -------------------------------------------------------------
st.title("Cybersecurity Quiz Platform")

mode = st.sidebar.selectbox("Select Mode:", ["Teacher", "Student"])


# ============================
# TEACHER MODE
# ============================
if mode == "Teacher":
    st.header("Teacher Login")

    password = st.text_input("Enter Teacher Password:", type="password")
    if password != "admin123":
        st.warning("Enter correct password to continue.")
        st.stop()

    st.success("Login successful ✔")
    st.header("Teacher Dashboard")

    st.subheader("Quiz Information")

    mandatory_topic = st.text_input("Enter Main Quiz Topic (Required)*")

    optional_text = st.text_area("Optional Supporting Text")

    optional_file = st.file_uploader(
        "Upload Optional Document (PDF, TXT, DOCX)",
        type=["pdf", "txt", "docx"]
    )

    optional_file_text = ""

    # SAFE FILE READING
    if optional_file:
        try:
            if optional_file.type == "text/plain":
                optional_file_text = optional_file.read().decode("utf-8")

            elif optional_file.type == "application/pdf":
                import PyPDF2
                reader = PyPDF2.PdfReader(optional_file)
                text = ""
                for p in reader.pages:
                    text += p.extract_text()
                optional_file_text = text

            elif optional_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                import docx
                doc = docx.Document(optional_file)
                optional_file_text = "\n".join([p.text for p in doc.paragraphs])

        except:
            st.error("⚠ Could not read file.")

    start_time = st.datetime_input("Quiz Start Time")
    end_time = st.datetime_input("Quiz End Time")

    # Generate Quiz
    if st.button("Generate Quiz"):
        if not mandatory_topic.strip():
            st.error("Main topic required.")
            st.stop()

        full_content = (
            f"MAIN TOPIC:\n{mandatory_topic}\n\n"
            f"OPTIONAL TEXT:\n{optional_text}\n\n"
            f"FILE CONTENT:\n{optional_file_text}"
        )

        with st.spinner("Generating quiz..."):
            quiz_text = safe_run(generate_quiz, full_content)
            if not quiz_text:
                st.stop()

            saved = safe_run(save_quiz_file, quiz_text, str(start_time), str(end_time))
            if not saved:
                st.stop()

            parsed = safe_run(parse_quiz, quiz_text)
            if not parsed:
                st.stop()

            st.success("Quiz Generated Successfully!")

            st.subheader("Preview of First 3 Questions:")
            for q in parsed[:3]:
                st.write(q["question"])
                st.write(q["options"])

    # View Results
    st.subheader("All Student Results")
    results = load_all_results()

    if results:
        df = pd.DataFrame([{
            "Student": r["student_name"],
            "Score": r["score"]
        } for r in results])

        st.table(df)

        if st.button("Download Marks Sheet"):
            filename = export_excel(results)
            if filename:
                with open(filename, "rb") as f:
                    st.download_button("Download Excel", f, filename)
    else:
        st.info("No student results yet.")


# ============================
# STUDENT MODE
# ============================
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

    # Timing Control
    if now < start_time:
        st.error(f"Quiz will start at: {start_time}")
        st.stop()

    if now > end_time:
        st.error(f"Quiz expired at: {end_time}")
        st.stop()

    parsed_questions = parse_quiz(quiz_text)
    if not parsed_questions:
        st.stop()

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
            try:
                if user_answers[i][0] == q["correct"]:
                    score += 1
            except:
                st.error("⚠ Error checking answers.")
                st.stop()

        st.success(f"{student_name}, you scored {score} / {len(parsed_questions)}")

        file_result = save_student_results(student_name, score, parsed_questions, user_answers)
        if file_result:
            st.info(f"Saved as: **{file_result}**")
