import firebase_admin
from firebase_admin import credentials, firestore
import streamlit as st
import json
import os
from typing import Dict, List, Optional
from datetime import datetime

class FirebaseService:
    """
    Firebase service for REClassroom data management.
    Handles scenarios, sessions, and interaction logging.
    """
    
    def __init__(self):
        self.db = None
        self._initialize_firebase()
    
    def _initialize_firebase(self):
        """Initialize Firebase app and Firestore client."""
        try:
            # Check if Firebase is already initialized
            if not firebase_admin._apps:
                # Try to get credentials from Streamlit secrets first
                if hasattr(st, 'secrets') and 'firebase' in st.secrets:
                    # Using Streamlit secrets (recommended for deployment)
                    firebase_config = dict(st.secrets["firebase"])
                    cred = credentials.Certificate(firebase_config)
                    firebase_admin.initialize_app(cred)
                elif os.path.exists("firebase-credentials.json"):
                    # Using local credentials file
                    cred = credentials.Certificate("firebase-credentials.json")
                    firebase_admin.initialize_app(cred)
                else:
                    # No credentials found
                    st.error("❌ Firebase credentials not found. Please configure Firebase.")
                    st.info("""
                    **To configure Firebase:**
                    
                    1. Go to [Firebase Console](https://console.firebase.google.com/)
                    2. Create a new project or select existing
                    3. Go to Project Settings > Service Accounts
                    4. Generate a new private key (JSON file)
                    5. Either:
                       - Save as `firebase-credentials.json` in project root, OR
                       - Add to Streamlit secrets (for deployment)
                    """)
                    return
            
            self.db = firestore.client()
            
        except Exception as e:
            st.error(f"Failed to initialize Firebase: {str(e)}")
            return
    
    def is_connected(self) -> bool:
        """Check if Firebase is properly connected."""
        return self.db is not None
    
    # SCENARIO MANAGEMENT
    
    def save_scenario(self, scenario_data: Dict) -> bool:
        """Save a scenario to Firestore."""
        if not self.is_connected():
            return False
            
        try:
            scenario_data['created_at'] = datetime.now()
            scenario_data['updated_at'] = datetime.now()
            
            # Save to 'scenarios' collection with scenario ID as document ID
            doc_ref = self.db.collection('scenarios').document(scenario_data['id'])
            doc_ref.set(scenario_data)
            return True
            
        except Exception as e:
            st.error(f"Failed to save scenario: {str(e)}")
            return False
    
    def get_scenario(self, scenario_id: str) -> Optional[Dict]:
        """Retrieve a specific scenario by ID."""
        if not self.is_connected():
            return None
            
        try:
            doc_ref = self.db.collection('scenarios').document(scenario_id)
            doc = doc_ref.get()
            
            if doc.exists:
                return doc.to_dict()
            return None
            
        except Exception as e:
            st.error(f"Failed to get scenario: {str(e)}")
            return None
    
    def list_scenarios(self) -> List[Dict]:
        """List all available scenarios."""
        if not self.is_connected():
            return []
            
        try:
            scenarios = []
            docs = self.db.collection('scenarios').stream()
            
            for doc in docs:
                scenario_data = doc.to_dict()
                scenarios.append(scenario_data)
            
            return scenarios
            
        except Exception as e:
            st.error(f"Failed to list scenarios: {str(e)}")
            return []
    
    def delete_scenario(self, scenario_id: str) -> bool:
        """Delete a scenario."""
        if not self.is_connected():
            return False
            
        try:
            self.db.collection('scenarios').document(scenario_id).delete()
            return True
            
        except Exception as e:
            st.error(f"Failed to delete scenario: {str(e)}")
            return False
    
    # SESSION MANAGEMENT
    
    def create_session(self, scenario_id: str, session_data: Dict) -> str:
        """Create a new learning session."""
        if not self.is_connected():
            return None
            
        try:
            session_data.update({
                'scenario_id': scenario_id,
                'created_at': datetime.now(),
                'updated_at': datetime.now(),
                'status': 'active'
            })
            
            # Auto-generate session ID
            doc_ref = self.db.collection('sessions').document()
            doc_ref.set(session_data)
            
            return doc_ref.id
            
        except Exception as e:
            st.error(f"Failed to create session: {str(e)}")
            return None
    
    def update_session(self, session_id: str, session_data: Dict) -> bool:
        """Update session data (e.g., dialogue history, requirements)."""
        if not self.is_connected():
            return False
            
        try:
            session_data['updated_at'] = datetime.now()
            
            doc_ref = self.db.collection('sessions').document(session_id)
            doc_ref.update(session_data)
            
            return True
            
        except Exception as e:
            st.error(f"Failed to update session: {str(e)}")
            return False
    
    def get_session(self, session_id: str) -> Optional[Dict]:
        """Retrieve session data."""
        if not self.is_connected():
            return None
            
        try:
            doc_ref = self.db.collection('sessions').document(session_id)
            doc = doc_ref.get()
            
            if doc.exists:
                return doc.to_dict()
            return None
            
        except Exception as e:
            st.error(f"Failed to get session: {str(e)}")
            return None
    
    # INTERACTION LOGGING
    
    def log_interaction(self, session_id: str, interaction_data: Dict) -> bool:
        """Log a single interaction (message exchange)."""
        if not self.is_connected():
            return False
            
        try:
            interaction_data.update({
                'session_id': session_id,
                'timestamp': datetime.now()
            })
            
            # Add to interactions subcollection
            self.db.collection('sessions').document(session_id).collection('interactions').add(interaction_data)
            
            return True
            
        except Exception as e:
            st.error(f"Failed to log interaction: {str(e)}")
            return False

# Global Firebase service instance
firebase_service = FirebaseService() 