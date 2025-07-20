import streamlit as st
from openai import OpenAI
from typing import List, Dict, Optional
from reclassroom.core.persona_engine import generate_system_prompt
from reclassroom.core.graph_state import GraphState
import json
from reclassroom.core.firebase_service import firebase_service

def generate_agent_response(state: GraphState) -> Dict:
    """
    Generates a response from the specified AI persona.
    This function now gets the speaker from the *first item* in the turn_roster.
    """
    if not state['turn_roster']:
        error_msg = "System Error: generate_agent_response called with an empty turn_roster."
        state['dialogue_history'].append({"role": "system", "content": error_msg})
        return {"dialogue_history": state['dialogue_history']}

    speaker = state['turn_roster'][0]
    project_context = state['project_context']
    history = state['dialogue_history']
    ai_response_style = state.get('ai_response_style', 'Normal')
    
    stakeholder_config = next((s for s in state['stakeholders'] if s['role'] == speaker), None)

    if not stakeholder_config:
        error_msg = f"System Error: Could not find configuration for stakeholder '{speaker}'."
        state['dialogue_history'].append({"role": "system", "content": error_msg})
        return {"dialogue_history": state['dialogue_history']}

    # Generate the persona-specific system prompt with new negotiation details.
    system_prompt = generate_system_prompt(
        stakeholder=stakeholder_config,
        all_stakeholders=state['stakeholders'],
        project_context=project_context,
        key_requirements=state.get('evaluation_criteria', {}).get('key_requirements', [])
    )
    
    messages = [{"role": "system", "content": system_prompt}]
    for msg in history:
        role = msg['role']
        if role == "student":
            api_role = "user"
            content = msg['content']
        else:
            api_role = "assistant"
            # Prepend the role to the content to avoid confusion in multi-agent turns
            content = f"**{role}:** {msg['content']}"
        
        messages.append({"role": api_role, "content": content})

    try:
        client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
        completion = client.chat.completions.create(
            model="gpt-4.1",
            messages=messages,
            temperature=0.7,
        )
        response_text = completion.choices[0].message.content

        new_message = {"role": speaker, "content": response_text}
        state['dialogue_history'].append(new_message)
        
        state['turn_roster'] = state['turn_roster'][1:]
        
        return {"dialogue_history": state['dialogue_history'], "turn_roster": state['turn_roster']}

    except Exception as e:
        error_message = f"Error for {speaker}: {e}"
        st.error(error_message)
        state['dialogue_history'].append({"role": "system", "content": error_message})
        # Even on error, we must modify the roster to prevent an infinite loop
        state['turn_roster'] = state['turn_roster'][1:]
        return {"dialogue_history": state['dialogue_history'], "turn_roster": state['turn_roster']}

def get_routing_choice(state: GraphState) -> Dict:
    """
    Determines which stakeholder(s) should speak next. It uses a rule-based check
    for general greetings, and an LLM call for topic-based routing.
    """
    history = state['dialogue_history']
    student_message = history[-1]['content'].lower().strip()
    stakeholder_roles = [s['role'] for s in state['stakeholders']]
    
    # --- Rule-based check for general greetings ---
    general_greetings = [
        "hi all", "hello all", "hi everyone", "hello everyone", "hey everyone",
        "how are you", "what do you all think", "your initial thoughts"
    ]
    # Check if the message is a greeting or a generic open-ended question
    if any(greeting in student_message for greeting in general_greetings) or student_message in ["hi", "hello", "hey"]:
        # If it's a general greeting, everyone responds. Bypass the LLM.
        return {"roster": stakeholder_roles, "is_concluding": False}

    # --- LLM-based routing for specific questions ---
    formatted_history = "\n".join([f"- {msg['role']}: {msg['content']}" for msg in history[-5:]])

    prompt = f"""
You are an expert moderator for a multi-agent meeting simulation. Your single most important task is to decide who speaks next based on the student's most recent message.

**Available Stakeholders:** {', '.join(stakeholder_roles)}
**Recent Conversation History:**
{formatted_history}

---
**YOUR TASK**
---
You will return a JSON object: `{{"roster": "...", "is_concluding": ...}}`.
Your primary goal is to identify which stakeholder is being addressed.

- If the student is addressing one or more stakeholders directly, put their role(s) in the "roster". You can use an informal name if you're not sure of the full title (e.g., "IT Security").
- If no one is being addressed directly, analyze the topic and put the most relevant stakeholder(s) on the roster.

You MUST respond with a single, valid JSON object.
"""

    try:
        client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
        completion = client.chat.completions.create(
            model="gpt-4.1",
            messages=[{"role": "system", "content": prompt.strip()}],
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        response_data = json.loads(completion.choices[0].message.content)
        
        roster_value = response_data.get("roster")
        is_concluding = response_data.get("is_concluding", False)

        if not roster_value:
            return {"roster": ["END"], "is_concluding": True}

        # Handle both string and list formats from the LLM for robustness
        llm_choices = []
        if isinstance(roster_value, str):
            llm_choices = [choice.strip() for choice in roster_value.split(',')]
        elif isinstance(roster_value, list):
            llm_choices = [str(choice).strip() for choice in roster_value]

        # Fuzzy match the LLM's output against the official roles
        validated_choices = []
        for choice in llm_choices:
            for official_role in stakeholder_roles:
                # If the AI's choice is a substring of the official role (case-insensitive)
                if choice.lower() in official_role.lower():
                    if official_role not in validated_choices: # Avoid duplicates
                        validated_choices.append(official_role)
        
        if not validated_choices:
            # Fallback if fuzzy matching fails to find anyone.
            return {"roster": ["END"], "is_concluding": True}
            
        return {"roster": validated_choices, "is_concluding": is_concluding}

    except Exception as e:
        st.error(f"Error in routing: {e}")
        return {"roster": ["END"], "is_concluding": True}

def conflict_check_agent(state: GraphState) -> Dict[str, str]:
    """
    Analyzes the list of elicited requirements for internal conflicts.
    The behavior of this agent changes based on the difficulty level.
    """
    difficulty = state.get('difficulty_level', 'Easy (Tutor Mode)')
    if difficulty == 'Hard (Expert Mode)':
        # In Hard mode, do not perform any conflict analysis.
        return {"negotiation_status": state.get('negotiation_status', {})}

    elicited_requirements = state.get('elicited_requirements', [])
    if not elicited_requirements:
        return {"negotiation_status": {}}

    # Convert the requirements to a simple list of strings for the AI
    req_list = [req['requirement'] for req in elicited_requirements]
    formatted_requirements = "\n".join(f"- {req}" for req in req_list)

    # Tailor the prompt based on the difficulty level
    if difficulty == 'Easy (Tutor Mode)':
        reason_instruction = 'For "Disputed" status, provide a brief, objective explanation of why these requirements conflict with each other.'
    else: # Medium (Hint Mode)
        reason_instruction = 'For "Disputed" status, the reason must be an empty string "".'

    prompt = f"""
You are a master requirements analyst. Your task is to perform a sophisticated conflict analysis on a list of elicited requirements. You must identify not only direct contradictions, but also instances where one requirement makes another difficult or impossible to implement due to constraints.

**List of Requirements to Analyze:**
---
{formatted_requirements}
---

**Your Task:**
Return a JSON object where each key is a requirement string from the list above, and the value is an object with "status" and "reason".

**Types of Conflicts to Detect:**

1.  **Direct Contradiction:** One requirement states 'X' and another states 'Not X'. (e.g., "The button must be green" vs. "The button must be blue").
2.  **Constraint Violation (Most Important):** A functional requirement (a feature) is in conflict with a non-functional requirement (a rule, constraint, or quality attribute). This is the most common and critical type of conflict.

**Statuses:**
- **"Disputed"**: The requirement either directly contradicts another or its implementation is constrained/blocked by a non-functional requirement on the list.
- **"Agreed"**: The requirement is a standalone statement that does not conflict with any others on this list.

**Reasoning Rule:**
{reason_instruction}

**Rules:**
1.  Your output MUST be a single, valid JSON object.
2.  The keys of the JSON object must exactly match the requirement strings from the list.
3.  Base your analysis ONLY on the internal consistency of the list provided.

**Example of Constraint Violation:**
- Requirement A: "The app must allow users to upload profile pictures."
- Requirement B: "The system must not store any user-generated content."
- **Analysis:** These are "Disputed". Requirement A is a feature that is blocked by the constraint in Requirement B. Your reason should state this conflict.
"""
    try:
        client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
        completion = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[{"role": "system", "content": prompt.strip()}],
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        new_status = json.loads(completion.choices[0].message.content)
        return {"negotiation_status": new_status}

    except Exception as e:
        st.error(f"Error in conflict check agent: {e}")
        return {"negotiation_status": state.get('negotiation_status', {})}


def ambiguity_scorer_agent(state: GraphState) -> Dict:
    """
    Analyzes the student's most recent message for ambiguity.
    """
    student_message = state['dialogue_history'][-1]['content']

    prompt = f"""
You are an expert in requirements engineering and communication. Your task is to analyze a student's question to a stakeholder and rate its ambiguity.

**Scoring Rubric (1-10 scale):**
- **1-3 (Low Ambiguity / Clear):** The question is specific, direct, and likely to elicit a concrete, actionable answer. It uses precise language and avoids jargon. (e.g., "What is the maximum budget allocated for the user authentication feature?", "Can the system handle 500 concurrent users with a response time under 200ms?")
- **4-7 (Moderate Ambiguity / Needs Clarification):** The question is on the right track but is somewhat vague or open-ended. It might use general terms or make assumptions. It requires the stakeholder to make interpretations. (e.g., "What are the security requirements?", "Tell me about the user interface.", "Can we make it user-friendly?")
- **8-10 (High Ambiguity / Vague):** The question is very unclear, broad, or confusing. It is unlikely to lead to a useful answer and may indicate the student doesn't know what to ask. (e.g., "What do you want?", "Is the system good?", "Any other requirements?")

**Student's Question:**
---
{student_message}
---

**Your Task:**
Based on the rubric, evaluate the student's question. You MUST respond with a single, valid JSON object containing two keys: "score" (an integer from 1-10) and "reason" (a brief, one-sentence explanation for your score).

Example Response:
{{
  "score": 6,
  "reason": "The question 'Tell me about the user interface' is moderately ambiguous because it's too broad and doesn't specify which aspect of the UI to focus on."
}}
"""
    try:
        client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
        completion = client.chat.completions.create(
            model="gpt-4.1",
            messages=[{"role": "system", "content": prompt.strip()}],
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        response_data = json.loads(completion.choices[0].message.content)
        
        score = response_data.get("score", 10)
        reason = response_data.get("reason", "No reason provided.")

        # Update state directly
        state['current_ambiguity_score'] = score
        state['ambiguity_score_reason'] = reason
        if 'ambiguity_history' not in state or state['ambiguity_history'] is None:
            state['ambiguity_history'] = []
        state['ambiguity_history'].append(score)

        return state

    except Exception as e:
        st.error(f"Error in ambiguity scorer: {e}")
        # Return a default high ambiguity score on error
        state['current_ambiguity_score'] = 10
        state['ambiguity_score_reason'] = f"An error occurred during analysis: {e}"
        if 'ambiguity_history' not in state or state['ambiguity_history'] is None:
            state['ambiguity_history'] = []
        state['ambiguity_history'].append(10)
        return state

def run_analysis_on_requirements(requirements: List[Dict], stakeholders: List[Dict], project_context: str) -> Optional[Dict]:
    """
    Analyzes a list of requirements for conflicts, without needing conversation history.
    This is designed to be called directly from the UI when requirements are updated.
    """
    if not requirements:
        return {}

    formatted_reqs = "\n".join([f"- {r['requirement']} (Source: {r['source']})" for r in requirements])
    stakeholder_list = ", ".join([s['role'] for s in stakeholders])

    prompt = f"""
You are a master requirements analyst. Your task is to analyze a definitive list of requirements and identify any conflicts between them based on the known stakeholders and project context.

**Project Context:**
{project_context}

**Stakeholders Involved:**
{stakeholder_list}

**List of Requirements to Analyze:**
---
{formatted_reqs}
---

**Your Task:**
Return a JSON object where each key is a requirement string (from the list above, exactly as written), and the value is ANOTHER JSON object with two keys: "status" and "reason".

**Statuses:**
- **"Disputed"**: The requirement directly conflicts with another requirement on the list, or with a known stakeholder's core interests.
- **"Agreed"**: The requirement is a standalone statement that does not conflict with any others.

**Reason:**
- For "Disputed" status, provide a brief, objective explanation of the conflict, referencing the source stakeholders if possible. (e.g., "The Student Life goal for an open 'event gallery' conflicts with IT Security's rule against storing user-generated content.").
- For "Agreed" status, the reason should be an empty string "".

**Rules:**
1.  Your output MUST be a single, valid JSON object.
2.  The top-level keys must be the full requirement strings from the list (do not include the source).
3.  The values must be objects containing "status" and "reason".

Example of a valid response format:
{{
  "The system must have a dark mode.": {{ "status": "Agreed", "reason": "" }},
  "All user-uploaded photos must be public.": {{ "status": "Disputed", "reason": "This conflicts with the IT Security requirement to not store user-generated content." }}
}}
"""
    try:
        client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
        completion = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[{"role": "system", "content": prompt.strip()}],
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        analysis_results = json.loads(completion.choices[0].message.content)
        return analysis_results

    except Exception as e:
        st.error(f"Error in requirements conflict analysis: {e}")
        return None


def run_evaluation_agent(session_data: Dict, scenario_data: Dict) -> Optional[Dict]:
    """
    Analyzes a student's final submission and generates a structured evaluation report.
    """
    # Extract data for the prompt
    final_spec = session_data.get('final_specification', {})
    student_reqs = final_spec.get('requirements', [])
    student_notes = final_spec.get('conflict_resolution_notes', '')
    
    eval_criteria = scenario_data.get('evaluation_criteria', {})
    key_reqs = eval_criteria.get('key_requirements', [])
    core_conflict = eval_criteria.get('core_conflict', '')
    
    # Get the full chat history from Firebase
    chat_history_list = firebase_service.get_session_interactions(session_data['id'])
    chat_history = "\n".join([f"- {msg.get('role', 'unknown')}: {msg.get('content', '')}" for msg in chat_history_list])

    prompt = f"""
You are a highly experienced professor of Software Engineering, specializing in Requirements Elicitation. Your task is to provide a fair and structured evaluation of a student's performance in a simulated requirements engineering exercise.

You will be given the instructor's answer key, the student's final submission, and the full transcript of their conversation with the AI stakeholders.

---
**INSTRUCTOR'S ANSWER KEY**
---
**1. Key Requirements the Student Should Have Identified:**
{chr(10).join(f'- {req}' for req in key_reqs)}

**2. The Core Conflict of the Scenario:**
{core_conflict}

---
**STUDENT'S SUBMISSION**
---
**1. Student's Final Requirements List:**
{json.dumps(student_reqs, indent=2)}

**2. Student's Conflict Resolution Notes:**
{student_notes}

---
**FULL CONVERSATION TRANSCRIPT**
---
{chat_history}

---
**YOUR EVALUATION TASK**
---
You must evaluate the student's submission based on three criteria. Provide a score from 1-5 for each, and detailed written feedback. Your response MUST be a single, valid JSON object.

**JSON Response Structure:**
{{
  "coverage_assessment": {{
    "score": <int 1-5>,
    "feedback": "<string>"
  }},
  "conflict_identification_assessment": {{
    "score": <int 1-5>,
    "feedback": "<string>"
  }},
  "solution_validity_assessment": {{
    "score": <int 1-5>,
    "feedback": "<string>"
  }},
  "overall_feedback": "<string>"
}}

**Criteria for Evaluation:**

**1. Coverage Assessment (Score 1-5):**
   - Compare the student's list to the instructor's key requirements.
   - How many of the key requirements did the student successfully elicit and document?
   - **Score 5:** Identified all key requirements.
   - **Score 1:** Identified none or very few.
   - **Feedback:** List which key requirements were found and which were missed.

**2. Conflict Identification Assessment (Score 1-5):**
   - Did the student correctly identify and articulate the "Core Conflict" described by the instructor?
   - Look for evidence in their conflict resolution notes and the conversation transcript.
   - **Score 5:** Clearly understood and described the core conflict.
   - **Score 1:** Showed no awareness of the conflict.
   - **Feedback:** Comment on how well they understood the central issue between stakeholders.

**3. Solution Validity Assessment (Score 1-5):**
   - Analyze the student's proposed solution in their notes and final requirements list.
   - Is it a valid and creative attempt to resolve the core conflict? Does it respect the stakeholders' non-negotiable constraints from the transcript?
   - **Score 5:** Proposed a creative, viable solution that respects all hard constraints.
   - **Score 1:** Proposed a solution that ignores the conflict or violates a key constraint.
   - **Feedback:** Provide a critique of their proposed solution.

**4. Overall Feedback:**
   - Write a brief, final summary of the student's performance, highlighting their strengths and areas for improvement.
"""
    try:
        client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
        completion = client.chat.completions.create(
            model="gpt-4.1",
            messages=[{"role": "system", "content": prompt.strip()}],
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        evaluation_report = json.loads(completion.choices[0].message.content)
        return evaluation_report
    except Exception as e:
        st.error(f"Error during AI evaluation: {e}")
        return None 