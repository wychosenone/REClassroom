import streamlit as st
import json
import os
import glob
from reclassroom.core.firebase_service import firebase_service

def app():
    st.title("REClassroom: Student Interaction Environment")

    # Check Firebase connection
    if not firebase_service.is_connected():
        st.error("❌ Firebase not connected. Please contact your instructor.")
        if firebase_service.get_error_message():
            st.error(firebase_service.get_error_message())
        return

    st.success("✅ Connected to Firebase")

    # --- SCENARIO LOADER ---
    scenarios = firebase_service.list_scenarios()
    if not scenarios:
        st.warning("No scenarios found. Please ask your instructor to create a scenario first.")
        return

    scenario_map = {scenario['id']: scenario for scenario in scenarios}
    
    # Use session state to keep track of selected scenario
    if 'selected_scenario_id' not in st.session_state:
        st.session_state.selected_scenario_id = list(scenario_map.keys())[0]

    def on_scenario_change():
        st.session_state.selected_scenario_id = st.session_state.scenario_selector
        if "messages" in st.session_state:
            del st.session_state["messages"] # Clear chat history on scenario change
        if "session_id" in st.session_state:
            del st.session_state["session_id"] # Reset session on scenario change

    selected_scenario_id = st.selectbox(
        "Select a Scenario to Begin", 
        options=list(scenario_map.keys()), 
        key='scenario_selector',
        on_change=on_scenario_change
    )
    st.session_state.selected_scenario_id = selected_scenario_id

    # --- LOAD AND DISPLAY SCENARIO ---
    if st.session_state.selected_scenario_id:
        scenario_data = scenario_map[st.session_state.selected_scenario_id]
        st.session_state.scenario_data = scenario_data
        
        st.header(f"Scenario: {scenario_data['id']}")
        
        with st.expander("Project Context", expanded=True):
            st.markdown(scenario_data['project_context'])

        st.subheader("Your Task")
        st.info("Your goal is to elicit requirements from the following stakeholders. Engage them in a conversation to understand their needs, goals, and constraints. Try to identify any conflicts and negotiate a solution.")
        
        st.subheader("Stakeholders")
        cols = st.columns(len(scenario_data['stakeholders']))
        for i, stakeholder in enumerate(scenario_data['stakeholders']):
            with cols[i]:
                with st.container(border=True):
                    st.markdown(f"**Role:** {stakeholder['role']}")
        
        st.markdown("---")

        # Initialize session if not exists
        if "session_id" not in st.session_state:
            session_data = {
                'student_id': 'anonymous',  # TODO: Add proper user authentication
                'dialogue_history': [],
                'elicited_requirements': [],
                'negotiation_status': {}
            }
            session_id = firebase_service.create_session(scenario_data['id'], session_data)
            if session_id:
                st.session_state.session_id = session_id
                st.info(f"🎯 New session started: {session_id[:8]}...")

        # --- CHAT INTERFACE ---
        st.header("Negotiation Room")

        # Initialize chat history
        if "messages" not in st.session_state:
            st.session_state.messages = []

        # Display chat messages from history on app rerun
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        # Accept user input
        if prompt := st.chat_input("What would you like to say?"):
            # Add user message to chat history
            st.session_state.messages.append({"role": "user", "content": prompt})
            # Display user message in chat message container
            with st.chat_message("user"):
                st.markdown(prompt)

            # Log interaction to Firebase
            if "session_id" in st.session_state:
                interaction_data = {
                    'user_input': prompt,
                    'response': '*(Placeholder - AI not connected)*',
                    'personas_involved': [s['role'] for s in scenario_data['stakeholders']]
                }
                firebase_service.log_interaction(st.session_state.session_id, interaction_data)

            # TODO: This is where the Multi-Agent Orchestration Core will be called.
            # For now, we'll just display a placeholder response.
            with st.chat_message("assistant"):
                placeholder_response = f"*(This is a placeholder. The AI personas are not yet connected. Your message '{prompt}' has been logged to Firebase.)*"
                st.markdown(placeholder_response)
                st.session_state.messages.append({"role": "assistant", "content": placeholder_response})

        # Session info sidebar
        if "session_id" in st.session_state:
            with st.sidebar:
                st.subheader("Session Info")
                st.text(f"Session ID: {st.session_state.session_id[:8]}...")
                st.text(f"Messages: {len(st.session_state.messages)}")
                st.text(f"Scenario: {scenario_data['id']}")
                
                if st.button("End Session"):
                    # Update session as completed
                    session_update = {
                        'status': 'completed',
                        'final_message_count': len(st.session_state.messages)
                    }
                    firebase_service.update_session(st.session_state.session_id, session_update)
                    
                    # Clear session
                    del st.session_state.session_id
                    del st.session_state.messages
                    st.success("Session ended!")
                    st.rerun()

if __name__ == '__main__':
    app() 