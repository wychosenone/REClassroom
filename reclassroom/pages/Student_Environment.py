import streamlit as st
import sys
import os
from google.cloud import firestore
import json
import pandas as pd

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from reclassroom.core.firebase_service import firebase_service
from reclassroom.core.persona_engine import generate_system_prompt
from reclassroom.core.orchestration import conversation_graph
from reclassroom.core.agent_utils import run_evaluation_agent
from typing import Optional, Dict, List
from datetime import datetime, timezone

def get_or_create_session(scenario_id: str) -> Optional[str]:
    """
    Looks for an active session or creates a new one. This is designed
    to be robust against Streamlit re-runs.
    """
    session_key = f"session_id_{scenario_id}"
    
    if session_key in st.session_state and st.session_state[session_key]:
        return st.session_state[session_key]

    with st.spinner("Connecting to session..."):
        try:
            # Check Firebase for an existing active session
            active_session_id = firebase_service.find_active_session(scenario_id)
        except Exception as e:
            st.error("A database error occurred while searching for an active session.")
            st.warning(
                "This is often caused by a missing **composite index** in your Firestore database. "
                "Please check the terminal or logs where your Streamlit app is running. "
                "Firestore usually provides a direct link to create the necessary index."
            )
            st.code(f"Error details: {str(e)}", language="text")
            return None

        if active_session_id:
            st.session_state[session_key] = active_session_id
            # Load existing messages for that session
            interactions = firebase_service.get_session_interactions(active_session_id)
            if 'messages' not in st.session_state or not st.session_state.messages:
                 st.session_state.messages = [
                    {"role": i['role'], "content": i['content']} for i in interactions
                ]
            st.toast("Resumed existing session.")
            return active_session_id
        else:
            # No active session found, so create a new one
            session_data = {
                'student_id': 'anonymous',
                'scenario_id': scenario_id,
                'elicited_requirements': [],
                'negotiation_status': {},
                'difficulty_level': st.session_state.scenario_data.get('difficulty_level', 'Easy (Tutor Mode)'), # Add difficulty
            }
            new_session_id = firebase_service.create_session(scenario_id, session_data)
            if new_session_id:
                st.session_state[session_key] = new_session_id
                st.session_state.messages = []
                st.toast("Started a new session!")
                return new_session_id
            else:
                st.error("Fatal Error: Failed to create a new session in Firebase.")
                return None

def render_ambiguity_monitor(session_data: Dict):
    """Renders the ambiguity progress bar and reasoning based on difficulty."""
    difficulty = session_data.get('difficulty_level', 'Easy (Tutor Mode)')
    if difficulty == 'Hard (Expert Mode)':
        return # Do not render for experts

    st.sidebar.subheader("Question Clarity Score")
    
    score = session_data.get('current_ambiguity_score')
    reason = session_data.get('ambiguity_score_reason')

    if score is None:
        st.sidebar.info("Ask a question to see your clarity score.")
        return

    # Score is 1-10, where 1 is best (least ambiguous).
    # We want the progress bar to be full for a score of 1.
    progress_value = (11 - score) / 10.0
    
    # Define color based on score
    if score <= 3:
        color = "green"
    elif score <= 7:
        color = "orange"
    else:
        color = "red"

    st.sidebar.progress(progress_value)
    st.sidebar.markdown(f"**Ambiguity Level: {score}/10** ({'Low' if color == 'green' else 'Moderate' if color == 'orange' else 'High'} Ambiguity)")

    if reason and difficulty == 'Easy (Tutor Mode)':
        with st.sidebar.expander("See AI's Reasoning"):
            st.info(reason)

def render_conflict_dashboard(session_data: Dict):
    """Renders the conflict status dashboard based on difficulty."""
    difficulty = session_data.get('difficulty_level', 'Easy (Tutor Mode)')
    if difficulty == 'Hard (Expert Mode)':
        return # Do not render for experts

    st.sidebar.subheader("Conflict Status")
    status = session_data.get('negotiation_status', {})
    
    if not status:
        st.sidebar.info("No key topics identified yet.")
        return

    for topic, details in status.items():
        state = details.get("status", "Unknown")
        reason = details.get("reason", "")

        if state == "Disputed":
            st.sidebar.warning(f"**{topic}:** {state} ⚠️")
            if reason and difficulty == 'Easy (Tutor Mode)':
                with st.sidebar.expander("Why is this a conflict?"):
                    st.info(reason)
        elif state == "Resolved" or state == "Agreed":
            st.sidebar.success(f"**{topic}:** {state} ✅")
        else:
            st.sidebar.markdown(f"**{topic}:** {state}")

def render_sidebar_tools(session_data: Dict, session_id: str, scenario_data: Dict):
    """Renders the 'Add New Requirement' form in the sidebar."""
    st.sidebar.markdown("---")
    st.sidebar.subheader("Add New Requirement")
    
    with st.sidebar.form("new_requirement_form", clear_on_submit=True):
        stakeholder_names = [p['role'] for p in scenario_data.get('stakeholders', [])]
        
        new_req_text = st.text_area("Requirement Description", key="sidebar_req_text")
        new_req_source = st.selectbox("Source Stakeholder", options=stakeholder_names, key="sidebar_req_source")

        submitted = st.form_submit_button("Save Requirement")
        if submitted:
            if new_req_text and new_req_source:
                new_requirement = {
                    "requirement": new_req_text,
                    "source": new_req_source,
                    "priority": "Medium",
                    "category": "Uncategorized",
                }
                
                updated_reqs = session_data.get('elicited_requirements', []) + [new_requirement]
                if firebase_service.update_session(session_id, {'elicited_requirements': updated_reqs}):
                    st.toast("Requirement saved!", icon="✅")
                    st.session_state.session_data['elicited_requirements'] = updated_reqs
                    st.rerun()
                else:
                    st.error("Failed to save requirement.")
            else:
                st.warning("Please provide a requirement description and select a source.")

def render_requirements_workbench(session_data: Dict, session_id: str, scenario_data: Dict):
    """
    Renders a unified, interactive workbench for viewing, editing, and finalizing
    elicited requirements. This is the primary student workspace.
    """
    st.subheader("Requirements Workbench")
    st.info("After interviewing stakeholders, use the form in the sidebar to record requirements. Then, categorize, prioritize, and edit them in the table below.")

    # --- Section to Add New Requirements ---
    # This section has been moved to the render_sidebar_tools function.
    
    st.markdown("---")

    # --- Data Preparation for Rich Display ---
    requirements = session_data.get('elicited_requirements', [])
    negotiation_status = session_data.get('negotiation_status', {})
    
    processed_reqs = []
    if requirements:
        for req in requirements:
            # Ensure 'category' and 'priority' keys exist for backward compatibility
            req['category'] = req.get('category', "Uncategorized")
            req['priority'] = req.get('priority', "Medium")
            
            # Determine conflict status
            req_status = "N/A"
            # The keys of negotiation_status are now the full requirement strings.
            req_text = req['requirement']
            if req_text in negotiation_status:
                details = negotiation_status[req_text]
                state = details.get("status", "Unknown")
                # Updated to use the new "Agreed" status.
                req_status = f"{state} {'⚠️' if state == 'Disputed' else '✅' if state == 'Agreed' else '💬'}"
            
            req['status'] = req_status
            processed_reqs.append(req)

    # --- Interactive Requirements Table (outside the form) ---
    st.markdown("##### Elicited Requirements")

    with st.expander("What do the requirement categories mean?"):
        st.markdown(
            """
            - **Business Need:** The highest-level, often abstract, goals of the client. (e.g., 'I want an app that helps me save money'). These are often imprecise and can be a source of conflict.
            - **User Need:** Describes a specific task a user must complete to achieve the business need. (e.g., 'The user needs to be able to compare prices of different items').
            - **Functional Requirement:** A specific, testable statement about what the system **must do**. (e.g., 'The system shall provide a feature to sort items by price').
            - **Non-Functional Requirement:** Defines a quality or constraint on the system—how it **should be**. (e.g., 'The page must load in under 2 seconds', 'The system must use university SSO').
            - **To Be Clarified:** Requirements that are still ambiguous or need more details.
            """
        )

    if not processed_reqs:
        st.info("No requirements saved yet. Use the form above to add one.")
    
    edited_df = st.data_editor(
        pd.DataFrame(processed_reqs),
        column_config={
            "requirement": st.column_config.TextColumn("Requirement (Editable)", width="large"),
            "source": "Source Stakeholder",
            "priority": st.column_config.SelectboxColumn(
                "Priority", options=["High", "Medium", "Low"], required=True,
            ),
            "category": st.column_config.SelectboxColumn(
                "Category", options=["Uncategorized", "Business Need", "User Need", "Functional", "Non-Functional", "To Be Clarified"], required=True,
            ),
            "status": st.column_config.TextColumn("Conflict Status")
        },
        use_container_width=True,
        hide_index=True,
        key="requirements_editor",
        column_order=("status", "requirement", "priority", "category", "source")
    )

    if st.button("Save Changes to Requirements"):
        with st.spinner("Saving..."):
            df_to_save = edited_df.drop(columns=['status'], errors='ignore')
            updated_reqs_data = df_to_save.to_dict('records')
            
            if firebase_service.update_session(session_id, {'elicited_requirements': updated_reqs_data}):
                st.success("Changes saved!")
                st.rerun()
            else:
                st.error("Failed to save changes.")


    # --- Final Submission Form ---
    with st.form("workbench_form"):
        st.markdown("---")
        st.subheader("Conflict Resolution Notes")
        conflict_notes = st.text_area(
            "Explain how you identified and resolved conflicts between stakeholders. (e.g., 'The Head Librarian's budget concerns were addressed by proposing a phased MVP approach, which the IT Specialist agreed was technically feasible.')",
            height=200,
            value=session_data.get('final_specification', {}).get('conflict_resolution_notes', '')
        )

        submitted = st.form_submit_button("Submit Final Specification and End Session", type="primary")

        if submitted:
            with st.spinner("Submitting and ending session..."):
                # The `edited_df` variable holds the current visual state of the editor
                df_to_save = edited_df.drop(columns=['status'], errors='ignore')
                final_reqs_data = df_to_save.to_dict('records')

                final_specification = {
                    "requirements": final_reqs_data,
                    "conflict_resolution_notes": conflict_notes,
                    "submitted_at": datetime.now(timezone.utc)
                }
                
                # First, save the student's submission
                session_update = {
                    'status': 'completed',
                    'final_specification': final_specification,
                    'elicited_requirements': final_reqs_data, # Overwrite with final edited list
                    'final_message_count': len(st.session_state.get('messages', [])),
                    'total_duration': str(datetime.now(timezone.utc) - st.session_state.session_data['created_at'].replace(tzinfo=timezone.utc))
                }

                if firebase_service.update_session(session_id, session_update):
                    st.success("Submission saved! Now running AI evaluation...")
                    
                    # Now, run the evaluation agent
                    current_session_data = firebase_service.get_session(session_id)
                    evaluation_report = run_evaluation_agent(current_session_data, scenario_data)
                    
                    if evaluation_report:
                        # Save the evaluation report back to Firebase
                        firebase_service.update_session(session_id, {'final_evaluation': evaluation_report})
                        st.success("AI Evaluation Complete!")
                        st.balloons()

                        # Display final metrics to the student as a receipt
                        final_session_data = firebase_service.get_session(session_id)
                        duration_str = final_session_data.get('total_duration', 'N/A')
                        if '.' in duration_str:
                            duration_str = duration_str.split('.')[0]
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("Total Session Duration", duration_str)
                        with col2:
                            st.metric("Total Interactions", final_session_data.get('final_message_count', 'N/A'))

                    else:
                        st.error("The AI evaluator failed to generate a report.")

                    # Clean up session state
                    session_key = f"session_id_{scenario_data['id']}"
                    for key in [session_key, 'messages', 'finalizing_session', 'session_started', 'current_scenario_id_for_session', 'requirements_editor']:
                        if key in st.session_state:
                            del st.session_state[key]
                    
                    st.success("Successfully submitted! Your session has ended.")
                    st.balloons()
                    st.rerun()
                else:
                    st.error("Failed to submit specification. Please try again.")

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
        """
        When the user selects a new scenario, reset the session state.
        This will hide the chat interface and require the user to explicitly
        start the new session via the button.
        """
        st.session_state.session_started = False
        
        # We must clear all session-specific data when the scenario changes.
        for key in ['messages', 'session_data']:
            if key in st.session_state:
                del st.session_state[key]
        
        # Update to the new selection
        st.session_state.selected_scenario_id = st.session_state.scenario_selector

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
        st.info("Your goal is to elicit requirements from the following stakeholders. Engage them in a conversation to understand their needs, goals, and constraints. Try to identify any conflicts and ask clarifying questions to understand their source.")
        
        with st.expander("Workflow Guide: How to Complete This Scenario", expanded=True):
            st.markdown(
                """
                Follow these 5 steps to successfully complete the exercise:

                1.  Converse with Stakeholders:
                    Use the main chat window at the bottom of the page to interview the AI personas. Your goal is to understand their needs, goals, and constraints. Ask clear, specific questions.

                2.  Document Requirements:
                    As you discover requirements, use the **"Add New Requirement"** form in the "Requirements Workbench" section below to record them. Don't worry about getting them perfect at first—you can edit them in the next step.

                3.  Categorize and Prioritize:
                    In the **"Elicited Requirements"** table, use the editable columns to set the `Priority` and `Category` for each requirement you've documented. This is a critical analysis step.

                4.  Identify & Resolve Conflicts:
                    As you talk to more stakeholders, the system will automatically check for conflicts between your documented requirements. 
                    - If a **Disputed** status appears, you've found a conflict! 
                    - Use the chat to ask clarifying questions and figure out a solution. 
                    - Once you have a plan, describe it in the **"Conflict Resolution Notes"** text box at the very bottom of the page.

                5.  Submit Your Final Specification: 
                    When you have a complete list of requirements and have documented your conflict resolution plan, click the final **"Submit"** button to end the session and receive your AI-generated evaluation.
                """
            )

        st.subheader("Stakeholders")
        cols = st.columns(len(scenario_data['stakeholders']))
        for i, stakeholder in enumerate(scenario_data['stakeholders']):
            with cols[i]:
                with st.expander(f"**Role: {stakeholder['role']}**", expanded=False):
                    st.markdown(f"**Background:** {stakeholder['attributes'].get('background', 'No background provided.')}")
        
        st.markdown("---")

        # --- SESSION START ---
        if st.button(f"Start / Resume Session for '{scenario_data['id']}'", type="primary"):
            st.session_state.session_started = True
            st.session_state.current_scenario_id_for_session = scenario_data['id']
        
        # Only show the chat interface if the session has been started for the current scenario
        if st.session_state.get("session_started") and st.session_state.get("current_scenario_id_for_session") == scenario_data['id']:
            session_id = get_or_create_session(scenario_data['id'])
            
            if not session_id:
                st.error("Could not establish a session. Please refresh the page.")
                return
            
            # ALWAYS fetch the latest session data from Firebase to ensure the UI is in sync.
            # This is the single source of truth for the start of a turn.
            st.session_state.session_data = firebase_service.get_session(session_id)

            if not st.session_state.session_data:
                st.error("Could not load session data. Please refresh the page.")
                # Attempt to clear session to allow for a fresh start
                st.session_state.session_started = False
                if 'session_data' in st.session_state:
                    del st.session_state.session_data
                st.rerun()

            # The main UI is now a single, unified view. No more finalization mode.
            # --- Session Info Sidebar ---
            with st.sidebar:
                st.subheader("Active Session Info")
                st.text(f"Session ID: {session_id[:8]}...")
                messages_list = st.session_state.get('messages', [])
                st.text(f"Messages: {len(messages_list)}")
                st.text(f"Scenario: {st.session_state.selected_scenario_id}")
                
                st.markdown("---")
                if st.button("Restart Session", type="secondary", help="This will delete your current progress for this session and start over."):
                    with st.spinner("Restarting session..."):
                        if firebase_service.delete_session_and_subcollections(session_id):
                            # Define all session-specific keys to clear from the state
                            keys_to_delete = [
                                f"session_id_{scenario_data['id']}", 
                                'messages', 
                                'session_data', 
                                'session_started', 
                                'current_scenario_id_for_session', 
                                'sidebar_req_text', 
                                'sidebar_req_source', 
                                'requirements_editor'
                            ]
                            
                            for key in keys_to_delete:
                                if key in st.session_state:
                                    del st.session_state[key]
                            
                            st.success("Session restarted!")
                            st.rerun()
                        else:
                            st.error("Failed to restart the session. Please refresh the page.")

                # Render the dashboards from session_state's data
                render_ambiguity_monitor(st.session_state.session_data)
                render_conflict_dashboard(st.session_state.session_data)
                
                # Render the new requirement form in the sidebar
                render_sidebar_tools(st.session_state.session_data, session_id, scenario_data)
                
            # --- MAIN WORKBENCH AND CHAT AREA ---
            # Display the unified workbench above the chat, using the reliable session_state
            render_requirements_workbench(st.session_state.session_data, session_id, scenario_data)

            st.markdown("---")
            st.subheader("Conversation")

            if "messages" not in st.session_state:
                st.session_state.messages = []

            # Display chat messages from history
            for message in st.session_state.messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

            # Accept user input
            if prompt := st.chat_input("What would you like to say?"):
                st.session_state.messages.append({"role": "student", "content": prompt})
                with st.chat_message("student"):
                    st.markdown(prompt)

                with st.spinner("AI is thinking..."):
                    history_len_before = len(st.session_state.messages)

                    initial_state = {
                        "project_context": st.session_state.scenario_data['project_context'],
                        "stakeholders": st.session_state.scenario_data['stakeholders'],
                        "evaluation_criteria": st.session_state.scenario_data.get('evaluation_criteria', {}),
                        "dialogue_history": st.session_state.messages,
                        "turn_roster": [],
                        "is_concluding_turn": False,
                        # Read from st.session_state, not directly from Firebase, to ensure consistency
                        "negotiation_status": st.session_state.session_data.get('negotiation_status', {}),
                        # Initialize ambiguity fields
                        "current_ambiguity_score": st.session_state.session_data.get('current_ambiguity_score', None),
                        "ambiguity_score_reason": st.session_state.session_data.get('ambiguity_score_reason', ""),
                        "ambiguity_history": st.session_state.session_data.get('ambiguity_history', []),
                        "difficulty_level": st.session_state.session_data.get('difficulty_level', 'Easy (Tutor Mode)'),
                    }

                    # Switch from the complex `stream` to the robust `invoke` to ensure the final state is always captured.
                    final_state = conversation_graph.invoke(initial_state)

                    # Display all new messages generated during the turn.
                    new_messages = final_state['dialogue_history'][history_len_before:]
                    for msg in new_messages:
                        with st.chat_message(name=msg['role']):
                            st.markdown(f"**{msg['role']}:** {msg['content']}")

                    if final_state:
                        # Update the single source of truth in st.session_state first
                        st.session_state.messages = final_state['dialogue_history']
                        
                        # Update ambiguity score in session state and Firebase
                        st.session_state.session_data['current_ambiguity_score'] = final_state.get('current_ambiguity_score')
                        st.session_state.session_data['ambiguity_score_reason'] = final_state.get('ambiguity_score_reason')
                        st.session_state.session_data['ambiguity_history'] = final_state.get('ambiguity_history')
                        
                        updated_negotiation_status = final_state.get('negotiation_status', {})
                        st.session_state.session_data['negotiation_status'] = updated_negotiation_status
                        
                        # --- Save Final State to Firebase ---
                        # Now, save the updated status to Firebase for persistence
                        firebase_service.update_session(session_id, {
                            'negotiation_status': updated_negotiation_status,
                            'current_ambiguity_score': final_state.get('current_ambiguity_score'),
                            'ambiguity_score_reason': final_state.get('ambiguity_score_reason'),
                            'ambiguity_history': final_state.get('ambiguity_history'),
                        })
                        
                        # --- Requirement Extraction and Logging ---
                        # Log interactions
                        firebase_service.log_interaction(session_id, {'role': 'student', 'content': prompt})
                        new_ai_messages = st.session_state.messages[history_len_before:]
                        for msg in new_ai_messages:
                            firebase_service.log_interaction(session_id, {'role': msg['role'], 'content': msg['content']})
                        
                        st.rerun()
                    
                    # The sidebar logic has been moved out of the chat input block

# The if __name__ == '__main__' block is no longer needed in a multi-page app
# as Streamlit handles the page execution.
app() 