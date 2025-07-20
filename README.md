# REClassroom

REClassroom is a Python-based educational platform designed for simulating requirements elicitation (RE) scenarios. It provides a dynamic environment where students can practice and hone their RE skills by interacting with AI-powered stakeholder personas.

The application is built with Streamlit and features two distinct interfaces: one for instructors to design learning scenarios and one for students to engage with them.

## Core Features

*   **Instructor Environment**:
    *   Create, manage, and delete RE scenarios.
    *   Define a detailed project context, including name and description.
    *   Design multiple, distinct AI stakeholder personas for each scenario.
    *   Customize persona attributes like goals, background, communication style, and hidden constraints.
    *   Set an interaction limit for each scenario to define the session's scope.

*   **Student Environment**:
    *   Browse and select from available scenarios.
    *   Interact with multiple AI stakeholders in a seamless chat interface.
    *   Experience dynamic, context-aware conversations powered by an intelligent agent router.
    *   View the remaining interaction count to manage the session effectively.

*   **AI & Orchestration**:
    *   Uses OpenAI's language models to bring stakeholder personas to life.
    *   Employs LangGraph to orchestrate complex, multi-participant conversations.
    *   Features an intelligent router that analyzes the student's input to select the most appropriate stakeholder to respond, creating a natural dialogue flow.

*   **Persistence**:
    *   Utilizes Google Firebase (Firestore) to save and load all scenario and session data, ensuring persistence and scalability.
    *   Logs every student-agent interaction for review and analysis.

## Tech Stack

*   **Application Framework**: Streamlit
*   **AI & LLM Orchestration**: LangChain, LangGraph
*   **LLM Provider**: OpenAI
*   **Database**: Google Cloud Firestore
*   **Core Language**: Python

## Setup and Installation

To run REClassroom locally, follow these steps:

**1. Clone the Repository:**
```bash
git clone <your-repository-url>
cd REClassroom
```

**2. Set up a Python Environment:**
It is recommended to use a virtual environment.
```bash
python -m venv venv
source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
```

**3. Install Dependencies:**
```bash
pip install -r reclassroom/requirements.txt
```

**4. Configure Firebase:**
*   Obtain your Firebase service account credentials (a `.json` file) from your Firebase project settings.
*   Rename the file to `firebase-credentials.json` and place it in the root directory of this project.

**5. Configure OpenAI API Key:**
*   Create a file named `.streamlit/secrets.toml` in the project's root directory.
*   Add your OpenAI API key to this file as follows:
    ```toml
    OPENAI_API_KEY="your-key-here"
    ```

## How to Run

Once the setup is complete, you can run the Streamlit application from the root directory:

```bash
streamlit run main.py
```

The application will open in your web browser. You can navigate between the Student and Instructor environments using the sidebar.

## Project Structure

```
REClassroom/
├── main.py                    # Main application entry point
├── reclassroom/
│   ├── core/
│   │   ├── agent_utils.py     # Utilities for AI agents
│   │   ├── firebase_service.py # Handles all Firestore database operations
│   │   ├── graph_state.py     # Defines the state for the LangGraph orchestrator
│   │   ├── orchestration.py   # Manages the multi-agent conversation graph
│   │   └── persona_engine.py  # Dynamically generates system prompts for AI personas
│   ├── instructor_ui.py       # Defines the Streamlit UI for the instructor
│   ├── student_ui.py          # Defines the Streamlit UI for the student
│   └── requirements.txt       # Project dependencies
└── README.md                  # This file
```

## 🔥 Firebase Setup

### Step 1: Create Firebase Project

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Click "Add Project" or select an existing project
3. Enable Firestore Database:
   - Go to "Firestore Database" in the left sidebar
   - Click "Create database"
   - Choose "Start in test mode" for development
   - Select a region close to your users

### Step 2: Get Service Account Credentials

1. In Firebase Console, go to **Project Settings** (gear icon)
2. Navigate to **Service Accounts** tab
3. Click **Generate new private key**
4. Download the JSON file

### Step 3: Configure Credentials

**Option A: Local Development (Recommended)**
- Save the downloaded JSON file as `firebase-credentials.json` in the project root
- ⚠️ **Important**: Add `firebase-credentials.json` to your `.gitignore` file

**Option B: Streamlit Cloud Deployment**
- In Streamlit Cloud, go to your app settings
- Add the JSON content to Streamlit secrets as `firebase`
- Example secrets.toml format:
  ```toml
  [firebase]
  type = "service_account"
  project_id = "your-project-id"
  private_key_id = "your-private-key-id"
  private_key = "-----BEGIN PRIVATE KEY-----\nYOUR_PRIVATE_KEY\n-----END PRIVATE KEY-----\n"
  client_email = "your-service-account-email"
  client_id = "your-client-id"
  auth_uri = "https://accounts.google.com/o/oauth2/auth"
  token_uri = "https://oauth2.googleapis.com/token"
  auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
  client_x509_cert_url = "your-cert-url"
  ```

### Step 4: Firestore Collections

The application will automatically create these collections:
- `scenarios`: Stores instructor-created RE scenarios
- `sessions`: Tracks student learning sessions
- `interactions`: Logs individual message exchanges (subcollection of sessions)

## 📋 Data Structure

### Scenarios
```json
{
  "id": "scenario-name",
  "project_context": "Project description...",
  "stakeholders": [
    {
      "role": "Marketing Manager",
      "attributes": {
        "goals": "Increase user engagement...",
        "background": "5 years in marketing...",
        "communication_style": "Data-driven, direct",
        "domain_knowledge": "Digital marketing expertise...",
        "constraints": "Limited budget of $50k..."
      }
    }
  ],
  "created_at": "2024-01-01T00:00:00",
  "updated_at": "2024-01-01T00:00:00"
}
```

### Sessions
```json
{
  "scenario_id": "scenario-name",
  "student_id": "anonymous",
  "dialogue_history": [],
  "elicited_requirements": [],
  "negotiation_status": {},
  "status": "active",
  "created_at": "2024-01-01T00:00:00",
  "updated_at": "2024-01-01T00:00:00"
}
```

## 🎯 Usage

### For Instructors

1. Navigate to "👨‍🏫 Instructor Environment"
2. **Create Scenario Tab**:
   - Enter a unique Scenario ID
   - Describe the project context
   - Define stakeholder roles and attributes
   - Add/remove stakeholders as needed
   - Save to Firebase
3. **Manage Scenarios Tab**:
   - View all created scenarios
   - Delete scenarios if needed

### For Students

1. Navigate to "👩‍🎓 Student Environment"
2. Select a scenario from the dropdown
3. Review the project context and stakeholder roles
4. Start negotiating in the chat interface
5. Session data is automatically logged to Firebase

## Already Achieved

- **AI Persona Engine**: OpenAI integration for dynamic personas
- **Multi-Agent Orchestration**: LangGraph-based dialogue management
- **Requirements Tracking**: Automatic requirement extraction
- **Conflict Detection**: AI-powered negotiation analysis
- **User Authentication**: Proper student/instructor separation
- **Analytics Dashboard**: Session performance metrics

## 🛠️ Development

### Project Structure
```
REClassroom/
├── main.py                          # Application entry point
├── reclassroom/
│   ├── __init__.py
│   ├── requirements.txt             # Dependencies
│   ├── instructor_ui.py             # Instructor interface
│   ├── student_ui.py               # Student interface
│   └── core/
│       ├── __init__.py
│       ├── firebase_service.py      # Firebase integration
│       ├── persona_engine.py        # AI persona generation (placeholder)
│       └── orchestration.py         # Multi-agent management (placeholder)
├── scenarios/                       # Local JSON storage (deprecated)
└── firebase-credentials.json        # Firebase service account (add to .gitignore)
```

### Adding AI Personas

The next development phase will focus on:
1. OpenAI API integration in `persona_engine.py`
2. LangGraph implementation in `orchestration.py`
3. Dynamic prompt generation from scenario configurations
4. Stateful dialogue management

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License


## 🆘 Troubleshooting

### Firebase Connection Issues
- Verify credentials file exists and is valid JSON
- Check Firebase project permissions
- Ensure Firestore is enabled in your Firebase project

### Dependency Conflicts
- If you encounter protobuf version conflicts, they shouldn't affect functionality
- Consider using a virtual environment for cleaner dependency management

### Streamlit Issues
- Clear browser cache if UI behaves unexpectedly
- Restart the Streamlit server: `Ctrl+C` then `streamlit run main.py`

## 📞 Support

For questions or issues, please [create an issue](link-to-issues) in the repository. 