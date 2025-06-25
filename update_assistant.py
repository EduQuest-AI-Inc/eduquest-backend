#!/usr/bin/env python3
"""
Script to update the LTG assistant with proper JSON response format.
"""

from assistants import update_ltg_assistant

def main():
    # Update the specific assistant ID that's being used
    assistant_id = "asst_8z6tb1v1xrybumZE2QGYVp5m"
    print(f"Updating assistant {assistant_id}...")
    
    result = update_ltg_assistant(assistant_id)
    if result:
        print("Assistant updated successfully!")
    else:
        print("Failed to update assistant.")

if __name__ == "__main__":
    main() 