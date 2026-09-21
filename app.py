import streamlit as st
import pypdf
import json
import os
import math
import time  # NEW: Added for rate-limit delay tracking
from groq import Groq

# 1. Page Configuration (Updated to PDFtoQUIZ)
st.set_page_config(
    page_title="PDFtoQUIZ - Professional Exam Generator",
    page_icon="🩺",
    layout="centered"
)

# 2. Main Visual Titles (Updated to medquiz)
st.title("🩺 PDFtoQUIZ & medquiz")
st.write("Upload high-yield PDFs to generate structured, competitive clinical vignettes via PDFtoQUIZ.")

# 3. Setup API Key Securely
st.sidebar.header("Configuration")
api_key = st.sidebar.text_input("Enter Groq API Key", type="password")

if not api_key:
    st.info("Please enter your Groq API Key in the sidebar to begin.")
    st.stop()

# Initialize the official Groq Client
client = Groq(api_key=api_key)

# 4. PDF Text Extraction Function with Range Control
def extract_text_from_pdf(uploaded_file, extraction_mode, start_pg=1, end_pg=1):
    reader = pypdf.PdfReader(uploaded_file)
    total_pages = len(reader.pages)
    text = ""
    
    if extraction_mode == "Whole PDF":
        start_index = 0
        end_index = total_pages
    else:
        start_index = max(0, start_pg - 1)
        end_index = min(total_pages, end_pg)
        
    for page_num in range(start_index, end_index):
        content = reader.pages[page_num].extract_text()
        if content:
            text += content + "\n"
            
    return text, total_pages

# 5. Function to Generate an Offline Text File Report
def generate_text_report(quiz_data):
    report = "🩺 PDFtoQUIZ - NEET PG / INI-CET EXAM SHEET (medquiz)\n"
    report += "="*50 + "\n\n"
    
    report += "--- SECTION A: QUESTIONS ---\n\n"
    for idx, item in enumerate(quiz_data):
        report += f"Q{idx + 1}. {item['question']}\n"
        for o_idx, opt in enumerate(item['options']):
            letter = chr(65 + o_idx)
            report += f"   [{letter}] {opt}\n"
        report += "\n"
        
    report += "\n--- SECTION B: ANSWER KEY & RATIONALES ---\n\n"
    for idx, item in enumerate(quiz_data):
        correct_letter = chr(65 + item['correct_index'])
        report += f"Q{idx + 1} Correct Answer: [{correct_letter}]\n"
        report += f"Clinical Rationale: {item['rationale']}\n"
        report += "-"*30 + "\n\n"
        
    return report

# 6. App Layout & File Uploader
uploaded_file = st.file_uploader("Upload your Medical PDF notes / chapters", type=["pdf"])

if uploaded_file is not None:
    initial_reader = pypdf.PdfReader(uploaded_file)
    max_pages = len(initial_reader.pages)
    
    st.success(f"PDF uploaded successfully! Total pages: {max_pages}")
    st.subheader("Quiz Generation Settings")
    
    extraction_mode = st.radio(
        "Select Page Scope:",
        options=["Whole PDF", "Particular Page Range"],
        horizontal=True
    )
    
    start_page = 1
    end_page = max_pages
    
    if extraction_mode == "Particular Page Range":
        col1, col2 = st.columns(2)
        with col1:
            start_page = st.number_input("Start Page", min_value=1, max_value=max_pages, value=1)
        with col2:
            end_page = st.number_input("End Page", min_value=start_page, max_value=max_pages, value=min(start_page + 5, max_pages))
            
    num_questions = st.slider("Number of Questions to Generate", min_value=3, max_value=40, value=5)
    
    if st.button("Generate NEET PG / INI-CET Pattern Quiz 🚀"):
        with st.spinner("Extracting text and analyzing medical concepts..."):
            pdf_text, _ = extract_text_from_pdf(uploaded_file, extraction_mode, start_page, end_page)
            
        if not pdf_text.strip():
            st.error("No text could be extracted from the selected pages.")
            st.stop()
            
        # --- FIXED BATCH PARAMETERS TO PREVENT 429 RATE LIMITS ---
        BATCH_SIZE = 2  # Reduced from 5 to stay under the 1000 OTPM ceiling
        total_batches = math.ceil(num_questions / BATCH_SIZE)
        all_generated_questions = []
        
        progress_bar = st.progress(0.0)
        status_text = st.empty()
        
        for batch_idx in range(total_batches):
            current_batch_count = BATCH_SIZE if (batch_idx < total_batches - 1) else (num_questions - (batch_idx * BATCH_SIZE))
            
            status_text.write(f"Crafting batch {batch_idx + 1} of {total_batches} ({current_batch_count} vignettes)...")
            
            system_instruction = f"""
            You are an expert medical professor designing high-yield multiple-choice questions specifically for competitive exams like NEET PG and INI-CET. 
            Create exactly {current_batch_count} questions based strictly on the content extracted from the source material.
            1. Questions must use clinical vignettes (patient case descriptions with symptoms, vitals, labs).
            2. Provide exactly 4 options per question.
            3. Specify the exact zero-based index of the correct option (0 to 3).
            4. Provide a thorough clinical rationale analyzing why the correct option is true and why distractors are incorrect.
            
            Return ONLY a raw JSON array matching this exact schema layout without any markdown wrappers:
            [
              {{
                "question": "Clinical case description...",
                "options": ["Option A", "Option B", "Option C", "Option D"],
                "correct_index": 0,
                "rationale": "Comprehensive breakdown..."
              }}
            ]
            """
            
            try:
                response = client.chat.completions.create(
                    model='qwen/qwen3.8-27b',
                    messages=[
                        {"role": "system", "content": system_instruction},
                        {"role": "user", "content": f"Source Text Material:\n{pdf_text[:15000]}"}
                    ],
                    temperature=0.2,
                    response_format={"type": "json_object"}
                )
                
                parsed_response = json.loads(response.choices[0].message.content)
                
                if isinstance(parsed_response, dict) and "questions" in parsed_response:
                    batch_q = parsed_response["questions"]
                elif isinstance(parsed_response, dict) and len(parsed_response.keys()) == 1:
                    first_key = list(parsed_response.keys())
                    batch_q = parsed_response[first_key]
                else:
                    batch_q = parsed_response
                    
                if isinstance(batch_q, list):
                    all_generated_questions.extend(batch_q)
                else:
                    all_generated_questions.append(batch_q)
                    
                # NEW: Add a 2-second rate-limiting window cooldown between loops
                if batch_idx < total_batches - 1:
                    time.sleep(2.0)
                    
            except Exception as e:
                st.error(f"Failed to generate batch {batch_idx + 1}: {e}")
                break
                
            progress_bar.progress((batch_idx + 1) / total_batches)
            
        status_text.empty()
        progress_bar.empty()
        
        if all_generated_questions:
            st.session_state.quiz_data = all_generated_questions[:num_questions]
            st.session_state.user_answers = {}
            st.session_state.submitted = False
            st.success(f"Generated {len(st.session_state.quiz_data)} questions successfully!")

# 7. Render the Quiz Interface
if "quiz_data" in st.session_state and isinstance(st.session_state.quiz_data, list):
    st.write("---")
    st.header("📋 Examination Sheet")
    
    quiz_txt_content = generate_text_report(st.session_state.quiz_data)
    st.download_button(
        label="📥 Download Quiz and Answer Key (.txt)",
        data=quiz_txt_content,
        file_name="PDFtoQUIZ_assessment.txt",
        mime="text/plain"
    )
    st.write("")
    
    for idx, item in enumerate(st.session_state.quiz_data):
        st.markdown(f"**Q{idx + 1}. {item['question']}**")
        
        user_choice = st.radio(
            f"Select option for Q{idx + 1}:",
            options=item['options'],
            key=f"q_{idx}",
            index=None
        )
        st.session_state.user_answers[idx] = user_choice
        st.write("")

    if st.button("Submit Assessment"):
        st.session_state.submitted = True

# 8. Evaluation Logic Output
if st.session_state.get('submitted', False) and "quiz_data" in st.session_state:
    st.write("---")
    st.header("📊 Performance Breakdown")
    
    score = 0
    total = len(st.session_state.quiz_data)
    
    for idx, item in enumerate(st.session_state.quiz_data):
        correct_ans = item['options'][item['correct_index']]
        user_ans = st.session_state.user_answers.get(idx)
        
        st.markdown(f"#### Q{idx + 1}")
        if user_ans == correct_ans:
            st.success(f"Correct! Selected: {user_ans}")
            score += 1
        else:
            st.error(f"Incorrect. Selected: {user_ans} | Answer Key: {correct_ans}")
        
        st.info(f"**Clinical Rationale:** {item['rationale']}")
        st.write("---")
        
    st.metric(label="Your Exam Score", value=f"{score} / {total}")
