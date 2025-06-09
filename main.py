import streamlit as st
from reclassroom import instructor_ui, student_ui

def main():
    st.set_page_config(
        page_title="REClassroom",
        page_icon="📚",
        layout="wide"
    )

    PAGES = {
        "👨‍🏫 Instructor Environment": instructor_ui,
        "👩‍🎓 Student Environment": student_ui
    }

    st.sidebar.title('REClassroom Navigation')
    selection = st.sidebar.radio("Go to", list(PAGES.keys()))

    page = PAGES[selection]

    with st.spinner(f"Loading {selection}..."):
        page.app()

if __name__ == "__main__":
    main() 