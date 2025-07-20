import streamlit as st
import sys
import os

# This is a standard Python trick to fix module import issues in complex projects.
# It adds the project's root directory to the list of places Python looks for modules.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


st.set_page_config(
    page_title="REClassroom - Home",
    page_icon="🏠",
    layout="wide"
)

st.title("Welcome to REClassroom!")

st.markdown(
    """
    **REClassroom is a configurable learning environment designed to help students master the art of Requirements Elicitation with AI-powered personas.**
    
    This platform provides a safe and dynamic space to practice interviewing stakeholders, identifying conflicts, and refining specifications—core skills for any future software engineer or project manager.
    
    ---
    
    ### Please select your environment from the sidebar to begin:
    
    - **🎓 Student Environment:** If you are a student, start here to engage with an interactive elicitation scenario.
    - **🧑‍🏫 Instructor Panel:** If you are an instructor, use this panel to create, manage, and review scenarios and student submissions.
    
    *Select a page from the navigation bar on the left to get started.*
    """
) 