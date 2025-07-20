import streamlit as st
import sys
import os
import json
import pandas as pd
from datetime import datetime, timezone

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from reclassroom.core.firebase_service import firebase_service

def create_scenario_ui():
    """UI for creating new scenarios, structured as a guided wizard."""
    st.header("Scenario Builder Wizard")
    st.info("Follow the guided steps to create a new, detailed learning scenario for students.")

    # Use a unique session state key to avoid conflicts with other pages.
    if 'wizard_step' not in st.session_state:
        st.session_state.wizard_step = 1
    if 'scenario_builder_data' not in st.session_state:
        st.session_state.scenario_builder_data = {
            "id": "",
            "project_context": "",
            "stakeholders": [],
            "evaluation_criteria": {"key_requirements": [], "core_conflict": ""},
            "ai_response_style": "Normal",
            "difficulty_level": "Easy (Tutor Mode)"
        }
    if 'num_stakeholders' not in st.session_state:
        st.session_state.num_stakeholders = 2

    builder_data = st.session_state.scenario_builder_data

    # --- Step 1: Project Foundation ---
    if st.session_state.wizard_step == 1:
        st.subheader("Step 1 of 4: Project Foundation")
        
        builder_data['id'] = st.text_input(
            "Scenario ID", 
            value=builder_data.get('id', ''),
            help="A unique name for this scenario (e.g., 'library-mobile-app')."
        )
        builder_data['project_context'] = st.text_area(
            "Project Context", 
            value=builder_data.get('project_context', ''),
            height=150,
            help="Provide the overall project description, goals, and constraints that the student will see."
        )

        if st.button("Next: Create Stakeholders", type="primary"):
            if builder_data.get('id') and builder_data.get('project_context'):
                st.session_state.wizard_step = 2
                st.rerun()
            else:
                st.error("Please provide both a Scenario ID and Project Context before proceeding.")

    # --- Step 2: Create Stakeholders ---
    elif st.session_state.wizard_step == 2:
        st.subheader("Step 2 of 4: Create Stakeholders")
        
        col1, col2, _, _ = st.columns(4)
        with col1:
            if st.button("Add Stakeholder"):
                st.session_state.num_stakeholders += 1
                st.rerun()
        with col2:
            if st.button("Remove Last"):
                if st.session_state.num_stakeholders > 1:
                    st.session_state.num_stakeholders -= 1
                    if len(builder_data['stakeholders']) >= st.session_state.num_stakeholders:
                         builder_data['stakeholders'] = builder_data['stakeholders'][:st.session_state.num_stakeholders]
                    st.rerun()

        st.markdown("---")
        
        while len(builder_data['stakeholders']) < st.session_state.num_stakeholders:
            builder_data['stakeholders'].append({"role": "", "attributes": {}})

        cols = st.columns(st.session_state.num_stakeholders)
        for i in range(st.session_state.num_stakeholders):
            with cols[i]:
                stakeholder = builder_data['stakeholders'][i]
                st.markdown(f"##### Stakeholder {i+1}")
                stakeholder['role'] = st.text_input(
                    "Role", value=stakeholder.get('role', ''), key=f"role_{i}", 
                    placeholder="e.g., Head Librarian",
                    help="The official job title of the stakeholder (e.g., 'Director of IT Security'). This sets the foundation for their expertise and authority."
                )
                stakeholder['attributes']['goals'] = st.text_area(
                    "Goals", value=stakeholder.get('attributes', {}).get('goals', ''), key=f"goals_{i}", height=100, 
                    help="What does this person want to achieve? Define their primary objectives and success criteria. Good goals are specific and often quantifiable (e.g., 'Increase student engagement by 40%'). This is their core motivation."
                )
                stakeholder['attributes']['background'] = st.text_area(
                    "Background", value=stakeholder.get('attributes', {}).get('background', ''), key=f"background_{i}", height=100,
                    help="Describe their professional history, expertise, and personality (e.g., '15 years in management, MBA, methodical, impatient with vague ideas'). This determines HOW they will communicate and what they will focus on."
                )
                stakeholder['attributes']['non_negotiable_constraints'] = st.text_area(
                    "Non-Negotiable Constraints", value=stakeholder.get('attributes', {}).get('non_negotiable_constraints', ''), key=f"non_negotiable_{i}", height=100,
                    help="Define the absolute deal-breakers. These are the hard limits they WILL NOT compromise on (e.g., 'Cannot exceed $2.5M budget', 'System MUST use city SSO'). These are the primary source of conflict in the simulation."
                )
        
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Back to Foundation"):
                st.session_state.wizard_step = 1
                st.rerun()
        with col2:
            if st.button("Next: Set Learning Objectives", type="primary"):
                if all(s.get('role') for s in builder_data['stakeholders']):
                    st.session_state.wizard_step = 3
                    st.rerun()
                else:
                    st.error("Please provide a Role for every stakeholder.")

    # --- Step 3: Set Learning Objectives ---
    elif st.session_state.wizard_step == 3:
        st.subheader("Step 3 of 4: Set Learning Objectives")
        st.info("Define the pedagogical goals of the scenario. This information is the 'answer key' for the AI evaluator and will NOT be shown to the student.")

        st.markdown("#### The Core Conflict")
        builder_data['evaluation_criteria']['core_conflict'] = st.text_input(
            "Describe the central conflict you designed into the scenario.",
            value=builder_data.get('evaluation_criteria', {}).get('core_conflict', ''),
            help="e.g., 'The desire for a social feature vs. the strict security policy.'"
        )

        st.markdown("#### Key Requirements to Elicit")
        key_reqs_text = st.text_area(
            "List the critical requirements the student is expected to identify, one per line.",
            value="\n".join(builder_data.get('evaluation_criteria', {}).get('key_requirements', [])),
            height=250,
            help="The AI will check if these requirements are present in the student's final submission."
        )
        builder_data['evaluation_criteria']['key_requirements'] = [
            req.strip() for req in key_reqs_text.split('\n') if req.strip()
        ]

        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Back to Stakeholders"):
                st.session_state.wizard_step = 2
                st.rerun()
        with col2:
            if st.button("Next: Configure & Review", type="primary"):
                st.session_state.wizard_step = 4
                st.rerun()

    # --- Step 4: Configure & Review ---
    elif st.session_state.wizard_step == 4:
        st.subheader("Step 4 of 4: Configure & Review")
        st.info("Set the final AI parameters and review the complete scenario before saving.")

        col1, col2 = st.columns(2)
        with col1:
            builder_data['difficulty_level'] = st.selectbox(
                "Difficulty Level",
                ["Easy (Tutor Mode)", "Medium (Hint Mode)", "Hard (Expert Mode)"],
                index=["Easy (Tutor Mode)", "Medium (Hint Mode)", "Hard (Expert Mode)"].index(builder_data.get('difficulty_level', 'Easy (Tutor Mode)')),
                help="Control the level of scaffolding provided to the student."
            )
        with col2:
             builder_data['ai_response_style'] = st.selectbox(
                "AI Response Style", 
                ["Normal", "Concise", "Detailed"], 
                index=["Normal", "Concise", "Detailed"].index(builder_data.get('ai_response_style', 'Normal')),
                help="Control the verbosity of the AI stakeholders."
            )

        st.markdown("---")
        st.subheader("Scenario Review")
        scenario_for_review = builder_data
        st.markdown(f"**ID:** `{scenario_for_review.get('id', '_Not defined_')}`")
        st.markdown("**Project Context:**")
        st.info(scenario_for_review.get('project_context', '_Not defined_'))

        st.markdown("**Stakeholders:**")
        for s in scenario_for_review.get('stakeholders', []):
            if not s.get('role'): continue
            with st.expander(f"Role: **{s.get('role')}**"):
                st.markdown(f"**Goals:** {s.get('attributes', {}).get('goals', '_Not defined_')}")
                st.markdown(f"**Background:** {s.get('attributes', {}).get('background', '_Not defined_')}")
                st.markdown(f"**Non-Negotiable Constraints:** {s.get('attributes', {}).get('non_negotiable_constraints', '_Not defined_')}")
        
        st.markdown("**Core Conflict:**")
        st.info(scenario_for_review.get('evaluation_criteria', {}).get('core_conflict', '_Not defined_'))

        st.markdown("**Key Requirements:**")
        st.json(scenario_for_review.get('evaluation_criteria', {}).get('key_requirements', []))

        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Back to Learning Objectives"):
                st.session_state.wizard_step = 3
                st.rerun()
        with col2:
            if st.button("✅ Save Scenario to Firebase", type="primary"):
                scenario_to_save = builder_data.copy()
                scenario_to_save['stakeholders'] = [s for s in scenario_to_save['stakeholders'] if s.get('role')]
                
                if firebase_service.save_scenario(scenario_to_save):
                    st.success(f"Scenario '{scenario_to_save['id']}' saved successfully!")
                    # Reset for next time by deleting the specific keys
                    keys_to_delete = ['wizard_step', 'scenario_builder_data', 'num_stakeholders']
                    for key in keys_to_delete:
                        if key in st.session_state:
                            del st.session_state[key]
                    st.rerun()
                else:
                    st.error("Failed to save scenario to Firebase.")

def manage_scenarios_ui():
    """UI for managing existing scenarios."""
    st.header("Manage Existing Scenarios")
    
    scenarios = firebase_service.list_scenarios()
    
    if not scenarios:
        st.info("No scenarios found. Create your first scenario in the 'Create Scenario' tab.")
        return
    
    st.subheader(f"Found {len(scenarios)} scenarios:")
    
    for scenario in scenarios:
        with st.expander(f"📋 {scenario['id']} (Created: {scenario.get('created_at', 'Unknown')})"):
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.markdown(f"**Project Context:** {scenario.get('project_context', '')[:200]}...")
                stakeholder_roles = [s.get('role', 'Unnamed') for s in scenario.get('stakeholders', [])]
                st.markdown(f"**Stakeholders:** {', '.join(stakeholder_roles)}")
                st.json(scenario)
            
            with col2:
                if st.button(f"Delete", key=f"delete_{scenario['id']}", type="secondary"):
                    if firebase_service.delete_scenario(scenario['id']):
                        st.success(f"Scenario '{scenario['id']}' deleted!")
                        st.rerun()
                    else:
                        st.error("Failed to delete scenario.")

def render_submission_review():
    st.header("Review Student Submissions")
    st.info("Here you can review the final requirement specifications submitted by students at the end of their sessions.")

    completed_sessions = firebase_service.list_completed_sessions()

    if not completed_sessions:
        st.warning("No completed student submissions found.")
        return

    min_aware_datetime = datetime.min.replace(tzinfo=timezone.utc)
    completed_sessions.sort(key=lambda s: s.get('final_specification', {}).get('submitted_at', min_aware_datetime), reverse=True)

    session_options = {}
    for s in completed_sessions:
        submitted_at_obj = s.get('final_specification', {}).get('submitted_at')
        submitted_at_str = "No Submission Time"
        if submitted_at_obj and hasattr(submitted_at_obj, 'strftime'):
            submitted_at_str = submitted_at_obj.strftime('%Y-%m-%d %H:%M')
        
        session_key = f"{s.get('scenario_id', 'Unknown Scenario')} ({submitted_at_str})"
        session_options[session_key] = s
    
    selected_session_key = st.selectbox("Select a submission to review", options=list(session_options.keys()))

    if selected_session_key:
        selected_session = session_options[selected_session_key]
        final_spec = selected_session.get('final_specification')
        final_eval = selected_session.get('final_evaluation')

        st.markdown("---")
        st.subheader(f"Final Submission for Scenario: `{selected_session.get('scenario_id', 'N/A')}`")
        st.text(f"Submitted by: {selected_session.get('student_id', 'anonymous')}")
        st.text(f"Session ID: {selected_session.get('id', 'N/A')}")

        duration_str = selected_session.get('total_duration', 'N/A')
        if '.' in duration_str:
            duration_str = duration_str.split('.')[0]
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Session Duration", duration_str)
        with col2:
            st.metric("Total Interactions", selected_session.get('final_message_count', 'N/A'))

        if final_eval:
            st.markdown("---")
            st.subheader("AI Evaluation Report")
            
            def render_assessment(title, assessment_data):
                st.markdown(f"##### {title}")
                score = assessment_data.get('score', 0)
                feedback = assessment_data.get('feedback', 'No feedback provided.')
                
                if score >= 4:
                    color = "green"
                elif score == 3:
                    color = "orange"
                else:
                    color = "red"
                
                st.markdown(f"**Score: <span style='color:{color}; font-size: 1.2em;'>{score}/5</span>**", unsafe_allow_html=True)
                st.info(f"**Feedback:** {feedback}")

            if final_eval.get('coverage_assessment'):
                render_assessment("Coverage of Key Requirements", final_eval['coverage_assessment'])
            
            if final_eval.get('conflict_identification_assessment'):
                render_assessment("Conflict Identification", final_eval['conflict_identification_assessment'])

            if final_eval.get('solution_validity_assessment'):
                render_assessment("Solution Validity", final_eval['solution_validity_assessment'])

            st.markdown("##### Overall Feedback")
            st.success(final_eval.get('overall_feedback', 'No overall feedback provided.'))

        if final_spec:
            st.markdown("---")
            st.subheader("Student's Submission Details")
            st.markdown("#### Conflict Resolution Notes")
            st.success(final_spec.get('conflict_resolution_notes', "No notes provided."))

            st.markdown("#### Finalized Requirements")
            if final_spec.get('requirements'):
                st.dataframe(pd.DataFrame(final_spec['requirements']))
            else:
                st.warning("No requirements were finalized.")

            with st.expander("View Full Chat History for this Session"):
                interactions = firebase_service.get_session_interactions(selected_session.get('id'))
                if interactions:
                    for msg in interactions:
                        st.markdown(f"**{msg.get('role', 'unknown')}:**")
                        st.markdown(f"> {msg.get('content', '')}")
                else:
                    st.info("No chat history was logged for this session.")
        else:
            st.error("This session was marked as complete, but no final specification was found.")

def render_scenario_management():
    st.header("Scenario Management")
    tab1, tab2 = st.tabs(["Create Scenario", "Manage Scenarios"])
    
    with tab1:
        create_scenario_ui()
    
    with tab2:
        manage_scenarios_ui()

def app():
    st.title("REClassroom: Instructor Environment")

    if not firebase_service.is_connected():
        st.error("❌ Firebase not connected. Please ensure your `firebase-credentials.json` is correctly configured.")
        return
    st.success("✅ Connected to Firebase")
    
    tab1, tab2 = st.tabs(["Scenario Management", "Review Student Submissions"])

    with tab1:
        render_scenario_management()

    with tab2:
        render_submission_review()

app()