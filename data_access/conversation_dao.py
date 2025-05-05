from data_access.config import db  # Import Firestore instance

def add_conversation(student_id: str, thread_id: str, assistant: str, conversation_log: list):
    try:
        # Reference to the Firestore 'conversations' collection
        conversations_ref = db.collection("conversations")

        # Add a new conversation document
        conversations_ref.add({
            "student_id": student_id,
            "thread_id": thread_id,
            "assistant": assistant,
            "conversation_log": conversation_log
        })

    except Exception as e:
        print("Error adding conversation:", e)

def get_conversation(student_id: str, thread_id: str):
    try:
        # Reference to the Firestore 'conversations' collection
        conversations_ref = db.collection("conversations")

        # Query by student_id and thread_id
        query = conversations_ref.where("student_id", "==", student_id).where("thread_id", "==", thread_id).stream()

        # Retrieve and return the conversation data
        for doc in query:
            return doc.to_dict()  # Convert Firestore document to dictionary

        return None  # No conversation found
    except Exception as e:
        print("Error fetching conversation:", e)
        return None
    
def append_conversation(student_id: str, thread_id: str, new_message: dict):
    try:
        # Reference to the Firestore 'conversations' collection
        conversations_ref = db.collection("conversations")

        # Query the document with matching student_id and thread_id
        query = conversations_ref.where("student_id", "==", student_id).where("thread_id", "==", thread_id).stream()

        # Iterate through query results (should ideally be one document)
        for doc in query:
            doc_ref = conversations_ref.document(doc.id)  # Get document reference
            
            # Get existing conversation log
            conversation_data = doc.to_dict()
            conversation_log = conversation_data.get("conversation_log", [])

            # Append new message
            conversation_log.append(new_message)

            # Update Firestore document
            doc_ref.update({"conversation_log": conversation_log})

            print("Conversation updated successfully!")
            return True  # Success

        print("No matching conversation found.")
        return False  # No document matched
    except Exception as e:
        print("Error updating conversation:", e)
        return False  # Error occurred
    


'''
This function gets all conversation history for a student id and thread id to pass them to summary assistant.
'''
def get_all_conversations(student_id: str, thread_id: str):
    try:
        # Reference to the Firestore 'conversations' collection
        conversations_ref = db.collection("conversations")

        # Query all documents that match the student_id
        query = conversations_ref.where("student_id", "==", student_id).where("thread_id", "==", thread_id).stream()

        # Collect all conversation histories
        conversations = []
        for doc in query:
            conversations.append(doc.to_dict())

        return conversations  # Return list of all conversations
    except Exception as e:
        print("Error fetching all conversations:", e)
        return []  # Return empty list on error
    
    
    # thread_F1RAcknoubUuFssgliWJB2Vw
