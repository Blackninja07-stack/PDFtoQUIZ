import streamlit as st
import pypdf
import json
import os
import math
from groq import Groq

# Page Configuration and Setup
st.set_page_config(page_title="PDFtoQUIZ - Professional Exam Generator", page_icon="🩺", layout="centered")
st.title("🩺 PDFtoQUIZ & medquiz")
st.write("Upload high-yield PDFs to generate structured clinical vignettes.")

api_key = st.sidebar.text_input("Enter Groq API Key", type="password")
if not api_key:
    st.info("Please enter your Groq API Key in the sidebar to begin.")
    st.stop()

client = Groq(api_key=api_key)

def extract_text_from_pdf(uploaded_file, extraction_mode, start_pg=1, end_pg=1):
    reader = pypdf.PdfReader(uploaded_file)
    total_pages = len(reader.pages)
    text = ""
    start_index = 0 if extraction_mode == "Whole PDF" else max(0, start_pg - 1)
    end_index = total_pages if extraction_mode == "Whole PDF" else min(total_pages, end_pg)
    for page_num in range(start_index, end_index):
        content = reader.pages[page_num].extract_text()
        if content:
            text += content + "\n"
    return text, total_pages

uploaded_file = st.file_uploader("Upload Medical PDF", type=["pdf"])
if uploaded_file is not None:
    num_questions = st.slider("Total Questions to Generate", min_value=3, max_value=40, value=5)
    
    if st.button("Generate Quiz 🚀"):
        pdf_text, _ = extract_text_from_pdf(uploaded_file, "Whole PDF")
        BATCH_SIZE = 5
        total_batches = math.ceil(num_questions / BATCH_SIZE)
        all_generated_questions = []
        progress_bar = st.progress(0.0)
        
        for batch_idx in range(total_batches):
            current_batch_count = BATCH_SIZE if (batch_idx < total_batches - 1) else (num_questions - (batch_idx * BATCH_SIZE))
            try:
                response = client.chat.completions.create(
                    model='qwen/qwen3.8-27b',
                    messages=[
                        {"role": "system", "content": f"Create exactly {current_batch_count} MCQs in JSON format with 'question', 'options', 'correct_index', and 'rationale'."},
                        {"role": "user", "content": f"Source Material:\n{pdf_text[:15000]}"}
                    ],
                    response_format={"type": "json_object"}
                )
                parsed = json.loads(response.choices[0].message.content)
                batch_q = parsed.get("questions", parsed[list(parsed.keys())[0]] if isinstance(parsed, dict) else parsed)
                all_generated_questions.extend(batch_q if isinstance(batch_q, list) else [batch_q])
            except Exception as e:
                st.error(f"Error in batch {batch_idx + 1}: {e}")
                break
            progress_bar.progress((batch_idx + 1) / total_batches)
            
        if all_generated_questions:
            st.session_state.quiz_data = all_generated_questions[:num_questions]
            st.success(f"Generated {len(st.session_state.quiz_data)} questions successfully!")


