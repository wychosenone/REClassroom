import streamlit as st
import json
import os
from reclassroom.core.firebase_service import firebase_service

def app():
    st.title("REClassroom: Instructor Configuration Environment")

    # Check Firebase connection
    if not firebase_service.is_connected():
        st.error("❌ Firebase not connected. Please configure Firebase to continue.")
        return

    st.success("✅ Connected to Firebase")

    # Tabs for different instructor functions
    tab1, tab2 = st.tabs(["Create Scenario", "Manage Scenarios"])
    
    with tab1:
        create_scenario_ui()
    
    with tab2:
        manage_scenarios_ui()

def create_scenario_ui():
    """UI for creating new scenarios."""
    st.header("Create New Scenario")

    # --- SCENARIO PARAMETERS ---
    scenario_id = st.text_input("Scenario ID", help="A unique name for this scenario (e.g., 'ecommerce-checkout-feature').")

    st.subheader("C: Project Context")
    project_context = st.text_area("Provide the overall project description, goals, and constraints.", height=150)

    st.subheader("S: Stakeholder Roles & A: Persona Attributes")

    if 'num_stakeholders' not in st.session_state:
        st.session_state.num_stakeholders = 2

    def add_stakeholder():
        st.session_state.num_stakeholders += 1

    def remove_stakeholder():
        if st.session_state.num_stakeholders > 1:
            st.session_state.num_stakeholders -= 1
    
    col1, col2 = st.columns([1,1])
    with col1:
        st.button("Add Stakeholder", on_click=add_stakeholder)
    with col2:
        st.button("Remove Last Stakeholder", on_click=remove_stakeholder)

    personas = []
    cols = st.columns(st.session_state.num_stakeholders)

    for i in range(st.session_state.num_stakeholders):
        with cols[i]:
            st.markdown(f"---")
            st.markdown(f"##### Stakeholder {i+1}")
            role = st.text_input(f"Role", key=f"role_{i}", placeholder="e.g., Marketing Manager")
            
            st.markdown(f"###### Persona Attributes for {role if role else f'Stakeholder {i+1}'}")
            goals = st.text_area("Goals", key=f"goals_{i}", height=100, placeholder="Primary objectives and success criteria.")
            background = st.text_area("Background Profile", key=f"background_{i}", height=100, placeholder="Professional history, expertise.")
            communication_style = st.text_input("Communication Style", key=f"comm_style_{i}", placeholder="e.g., Formal, data-driven, prefers visuals.")
            domain_knowledge = st.text_area("Domain Knowledge", key=f"knowledge_{i}", height=100, placeholder="What they know about the project domain.")
            constraints = st.text_area("Constraints / Hidden Agendas", key=f"constraints_{i}", height=100, placeholder="e.g., Budget limits, specific feature requests, underlying motivations.")
            
            personas.append({
                "role": role,
                "attributes": {
                    "goals": goals,
                    "background": background,
                    "communication_style": communication_style,
                    "domain_knowledge": domain_knowledge,
                    "constraints": constraints,
                }
            })

    st.markdown("---")

    if st.button("Save Scenario to Firebase", type="primary"):
        if not scenario_id or not project_context or not all(p["role"] for p in personas):
            st.error("Please fill in the Scenario ID, Project Context, and all stakeholder roles before saving.")
        else:
            scenario_data = {
                "id": scenario_id,
                "project_context": project_context,
                "stakeholders": personas
            }
            
            # Save to Firebase
            if firebase_service.save_scenario(scenario_data):
                st.success(f"✅ Scenario '{scenario_id}' saved successfully to Firebase!")
                st.json(scenario_data)
                
                # Clear the form
                st.session_state.num_stakeholders = 2
                st.rerun()
            else:
                st.error("❌ Failed to save scenario to Firebase.")

def manage_scenarios_ui():
    """UI for managing existing scenarios."""
    st.header("Manage Existing Scenarios")
    
    # List all scenarios
    scenarios = firebase_service.list_scenarios()
    
    if not scenarios:
        st.info("No scenarios found. Create your first scenario in the 'Create Scenario' tab.")
        return
    
    st.subheader(f"Found {len(scenarios)} scenarios:")
    
    for scenario in scenarios:
        with st.expander(f"📋 {scenario['id']} (Created: {scenario.get('created_at', 'Unknown')})"):
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.markdown(f"**Project Context:** {scenario['project_context'][:200]}...")
                st.markdown(f"**Stakeholders:** {', '.join([s['role'] for s in scenario['stakeholders']])}")
                st.json(scenario)
            
            with col2:
                if st.button(f"Delete", key=f"delete_{scenario['id']}", type="secondary"):
                    if firebase_service.delete_scenario(scenario['id']):
                        st.success(f"Scenario '{scenario['id']}' deleted!")
                        st.rerun()
                    else:
                        st.error("Failed to delete scenario.")

if __name__ == '__main__':
    app() 