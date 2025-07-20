import firebase_admin
from firebase_admin import credentials, firestore
import json
import os
from typing import Dict, List, Optional
from datetime import datetime, timezone

class FirebaseService:
    """
    Firebase service for REClassroom data management.
    Handles scenarios, sessions, and interaction logging.
    """
    
    def __init__(self):
        self.db = None
        self.error_message = None
        self._initialize_firebase()
    
    def _initialize_firebase(self):
        """Initialize Firebase app and Firestore client."""
        try:
            # Check if Firebase is already initialized
            if not firebase_admin._apps:
                # Try to get credentials from environment variable or file
                if os.path.exists("firebase-credentials.json"):
                    # Using local credentials file
                    cred = credentials.Certificate("firebase-credentials.json")
                    firebase_admin.initialize_app(cred)
                else:
                    # No credentials found
                    self.error_message = "Firebase credentials not found. Please configure Firebase."
                    return
            
            self.db = firestore.client()
            
        except Exception as e:
            self.error_message = f"Failed to initialize Firebase: {str(e)}"
            return
    
    def is_connected(self) -> bool:
        """Check if Firebase is properly connected."""
        return self.db is not None
    
    def get_error_message(self) -> str:
        """Get the error message if connection failed."""
        return self.error_message
    
    # SCENARIO MANAGEMENT
    
    def save_scenario(self, scenario_data: Dict) -> bool:
        """Save a scenario to Firestore."""
        if not self.is_connected():
            return False
            
        try:
            scenario_data['created_at'] = datetime.now(timezone.utc)
            scenario_data['updated_at'] = datetime.now(timezone.utc)
            
            # Save to 'scenarios' collection with scenario ID as document ID
            doc_ref = self.db.collection('scenarios').document(scenario_data['id'])
            doc_ref.set(scenario_data)
            return True
            
        except Exception as e:
            print(f"Failed to save scenario: {str(e)}")
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
            print(f"Failed to get scenario: {str(e)}")
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
            print(f"Failed to list scenarios: {str(e)}")
            return []
    
    def delete_scenario(self, scenario_id: str) -> bool:
        """Delete a scenario."""
        if not self.is_connected():
            return False
            
        try:
            self.db.collection('scenarios').document(scenario_id).delete()
            return True
            
        except Exception as e:
            print(f"Failed to delete scenario: {str(e)}")
            return False
    
    # SESSION MANAGEMENT
    
    def create_session(self, scenario_id: str, session_data: Dict) -> str:
        """Create a new learning session."""
        if not self.is_connected():
            return None
            
        try:
            session_data.update({
                'scenario_id': scenario_id,
                'created_at': datetime.now(timezone.utc),
                'updated_at': datetime.now(timezone.utc),
                'status': 'active',
                'negotiation_status': {}, # Initialize the status tracker
            })
            
            # Auto-generate session ID
            doc_ref = self.db.collection('sessions').document()
            doc_ref.set(session_data)
            
            return doc_ref.id
            
        except Exception as e:
            print(f"Failed to create session: {str(e)}")
            return None
    
    def update_session(self, session_id: str, session_data: Dict) -> bool:
        """Update session data (e.g., dialogue history, requirements)."""
        if not self.is_connected():
            return False
            
        try:
            session_data['updated_at'] = datetime.now(timezone.utc)
            
            doc_ref = self.db.collection('sessions').document(session_id)
            doc_ref.update(session_data)
            
            return True
            
        except Exception as e:
            print(f"Failed to update session: {str(e)}")
            return False
    
    def get_session(self, session_id: str) -> Optional[Dict]:
        """Fetches a session document by its ID."""
        if not self.db:
            return None
        try:
            doc_ref = self.db.collection('sessions').document(session_id)
            doc = doc_ref.get()
            if doc.exists:
                session_data = doc.to_dict()
                # Manually add the document ID to the returned dictionary.
                # This is crucial for functions that need both the data and its ID.
                session_data['id'] = doc.id
                return session_data
            return None
        except Exception as e:
            self.error_message = f"Failed to get session: {e}"
    
    def find_active_session(self, scenario_id: str, student_id: str = "anonymous") -> Optional[str]:
        """
        Find an existing active session for a given scenario and student.
        Returns the session ID if found, otherwise None.
        
        NOTE: This query requires a composite index in Firestore. If the query fails,
        it will raise an exception.
        """
        if not self.is_connected():
            return None
        
        try:
            # Note: Using keyword arguments for 'where' to avoid UserWarning
            docs = (self.db.collection('sessions')
                   .where(filter=firestore.FieldFilter('scenario_id', '==', scenario_id))
                   .where(filter=firestore.FieldFilter('student_id', '==', student_id))
                   .where(filter=firestore.FieldFilter('status', '==', 'active'))
                   .limit(1)
                   .stream())
            
            for doc in docs:
                return doc.id # Return the ID of the first active session found
            return None
            
        except Exception as e:
            print(f"Error finding active session: {str(e)}")
            # Re-raise the exception to be handled by the caller.
            # This makes failures (like a missing index) visible.
            raise e
    
    def list_completed_sessions(self) -> List[Dict]:
        """List all sessions with a 'completed' status."""
        if not self.is_connected():
            return []
            
        try:
            completed_sessions = []
            docs = self.db.collection('sessions').where(filter=firestore.FieldFilter('status', '==', 'completed')).stream()
            
            for doc in docs:
                session_data = doc.to_dict()
                session_data['id'] = doc.id # Add the document ID to the data
                completed_sessions.append(session_data)
            
            return completed_sessions
            
        except Exception as e:
            print(f"Failed to list completed sessions: {str(e)}")
            return []

    def delete_session_and_subcollections(self, session_id: str) -> bool:
        """
        Deletes a session document and all documents in its 'interactions' subcollection.
        """
        if not self.is_connected():
            return False

        try:
            session_ref = self.db.collection('sessions').document(session_id)
            
            # Delete subcollection documents first
            interactions_ref = session_ref.collection('interactions')
            docs = interactions_ref.stream()
            for doc in docs:
                doc.reference.delete()
                
            # Finally, delete the parent session document
            session_ref.delete()
            
            return True
            
        except Exception as e:
            print(f"Failed to delete session and its subcollections: {str(e)}")
            return False
    
    # INTERACTION LOGGING
    
    def log_interaction(self, session_id: str, interaction_data: Dict) -> bool:
        """
        Log a single interaction message to a subcollection within a session.
        """
        if not self.is_connected():
            return False
            
        try:
            interaction_data['timestamp'] = datetime.now(timezone.utc)
            
            # Create a new document in the 'interactions' subcollection of the session
            self.db.collection('sessions').document(session_id).collection('interactions').add(interaction_data)
            
            return True
            
        except Exception as e:
            print(f"Failed to log interaction: {str(e)}")
            return False
    
    def get_session_interactions(self, session_id: str) -> List[Dict]:
        """Get all interactions for a session."""
        if not self.is_connected():
            return []
            
        try:
            interactions = []
            docs = (self.db.collection('sessions').document(session_id).collection('interactions')
                   .order_by('timestamp')
                   .stream())
            
            for doc in docs:
                interaction_data = doc.to_dict()
                interactions.append(interaction_data)
            
            return interactions
            
        except Exception as e:
            print(f"Failed to get session interactions: {str(e)}")
            return []

# Create a global instance
firebase_service = FirebaseService() 