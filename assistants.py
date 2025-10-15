import openai
from openai import OpenAI
import time
import os
import json
from dotenv import load_dotenv
from openai.types.shared_params.response_format_json_schema import ResponseFormatJSONSchema
import decimal

def convert_decimal(obj):
    if isinstance(obj, list):
        return [convert_decimal(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: convert_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, decimal.Decimal):
        return float(obj)
    else:
        return obj

load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
pre_calc = {
    'initiate': 'asst_bmsuvfNCaHJYmqTlnT52AzXE',
    'update': 'asst_oQlKvMpoDPp80zEabjvUiflj',
    'ltg': 'asst_1NnTwxp3tBgFWPp2sMjHU3Or'
}


# if student


def summarize_conversation(thread_id):  # will return two pd_dataframe(student_profile and quests)
    # Retrieve the summarization assistant
    assistant = openai.beta.assistants.retrieve("asst_IMuSxVprkgtBXH3xLXjMAvtB")
    thread = openai.beta.threads.retrieve(thread_id)
    thread_id = thread.id

    content = "Extract the student user (including strengths, weaknesses, interests, learning-style and long-term goal), and the 36 quests from previous conversation. "

    message = openai.beta.threads.messages.create(thread_id=thread_id, role="user", content=content)
    run = openai.beta.threads.runs.create(
        thread_id=thread_id,
        assistant_id=assistant.id
    )
    run_id = run.id
    while True:
        run_status = openai.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run_id)
        # print(f"Run status: {run_status.status}")
        if run_status.status == 'completed':
            break
        time.sleep(1)
    messages = openai.beta.threads.messages.list(thread_id=thread_id)
    last_message = messages.data[0]
    response = last_message.content[0].text.value

    return response


class ini_conv:
    def __init__(self, student, thread_id=None):
        self.student = student
        self.thread_id = thread_id
        self.assistant = openai.beta.assistants.retrieve("asst_bmsuvfNCaHJYmqTlnT52AzXE")

    def initiate(self):
        thread = openai.beta.threads.create()
        initial_message = f"Hello, I'm {self.student["first_name"] + " " + self.student["last_name"]}."
        self.thread_id = thread.id
        # Send the initial message to the thread
        message = openai.beta.threads.messages.create(thread_id=self.thread_id, role="user", content=initial_message)
        # Create a run to get the assistant's response
        run = openai.beta.threads.runs.create(
            thread_id=self.thread_id,
            assistant_id="asst_bmsuvfNCaHJYmqTlnT52AzXE"  # Pass the assistant ID as a string
        )
        run_id = run.id

        while True:
            run_status = openai.beta.threads.runs.retrieve(thread_id=self.thread_id, run_id=run_id)
            # print(f"Run status: {run_status.status}")
            if run_status.status == 'completed':
                break
            time.sleep(1)  # Wait for 1 second before checking again

            # Get messages once the run is completed
        messages = openai.beta.threads.messages.list(thread_id=self.thread_id)
        last_message = messages.data[0]
        response = last_message.content[0].text.value
        # self.conversation_log.append({"role": "assistant", "content": response})

        response_dict = json.loads(response)
        response_dict["thread_id"] = self.thread_id

        return response_dict

    def cont_conv(self, user_input):
        # self.conversation_log.append({"role": "user", "content": user_input})
        """"Returns message or updated student profile, + boolean indicating if the student profile is complete"""
        message = openai.beta.threads.messages.create(
            thread_id=self.thread_id,
            role="user",
            content=user_input
        )
        run = openai.beta.threads.runs.create(
            thread_id=self.thread_id,
            assistant_id=self.assistant.id
        )
        run_id = run.id

        while True:
            run_status = openai.beta.threads.runs.retrieve(thread_id=self.thread_id, run_id=run_id)
            # print(f"Run status: {run_status.status}")
            if run_status.status == 'completed':
                break
            time.sleep(1)  # Wait for 1 second before checking again

        messages = openai.beta.threads.messages.list(thread_id=self.thread_id)
        last_message = messages.data[0]
        response = last_message.content[0].text.value
        # self.conversation_log.append({"role": "assistant", "content": response})
        return_message = json.loads(response)

        strengths = return_message.get('Strengths', [])
        weaknesses = return_message.get('Weaknesses', [])
        interests = return_message.get('Interests', [])
        learning_styles = return_message.get('Learning_Styles', [])

        if not strengths or not weaknesses or not interests or not learning_styles:
            return return_message['response'], False, None
        else:
            profile = {
                "strength": strengths,
                "weakness": weaknesses,
                "interest": interests,
                "learning_style": learning_styles,
            }
            return return_message['response'], True, profile


class ltg:
    def __init__(self, student, assistant_id):
        self.student = student
        self.thread_id = None
        self.assistant = openai.beta.assistants.retrieve(assistant_id)

    def initiate(self):
        thread = openai.beta.threads.create()
        first_name = self.student["first_name"]
        last_name = self.student["last_name"]
        grade = self.student["grade"]
        strengths = ", ".join(self.student.get("strength", [])) if isinstance(self.student.get("strength"), list) else str(self.student.get("strength", ""))
        weaknesses = ", ".join(self.student.get("weakness", [])) if isinstance(self.student.get("weakness"), list) else str(self.student.get("weakness", ""))
        interests = ", ".join(self.student.get("interest", [])) if isinstance(self.student.get("interest"), list) else str(self.student.get("interest", ""))
        learning_style = ", ".join(self.student.get("learning_style", [])) if isinstance(self.student.get("learning_style"), list) else str(self.student.get("learning_style", ""))
        
        initial_message = f"Hello, I'm {first_name} {last_name}, in {grade}th grade. My strengths are {strengths}, my weaknesses are {weaknesses}, my interests are {interests}, and my learning style is {learning_style}. Please search the course materials and recommend 3 long-term goals for me that incorporate what I'll learn in this class."
        print(f"Initial message: {initial_message}")
        
        self.thread_id = thread.id
        # Send the initial message to the thread
        message = openai.beta.threads.messages.create(thread_id=self.thread_id, role="user", content=initial_message)
        # Create a run to get the assistant's response
        run = openai.beta.threads.runs.create(
            thread_id=self.thread_id,
            assistant_id=self.assistant.id
        )
        run_id = run.id

        while True:
            run_status = openai.beta.threads.runs.retrieve(thread_id=self.thread_id, run_id=run_id)
            if run_status.status == 'completed':
                break
            elif run_status.status in ['failed', 'cancelled', 'expired']:
                raise Exception(f"Run failed with status: {run_status.status}")
            time.sleep(1)
        
        messages = openai.beta.threads.messages.list(thread_id=self.thread_id)
        last_message = messages.data[0]
        response = last_message.content[0].text.value
        # self.conversation_log.append({"role": "assistant", "content": response})
        return_message = json.loads(response)
        return_message["thread_id"] = self.thread_id

        print(f"Raw LTG Assistant Response: {response}")

        # if "message" not in response_dict:
        #     response_dict["message"] = "I'm here to help you choose a long-term goal!"
        # if "chosen_goal" not in response_dict:
        #     response_dict["chosen_goal"] = None

        return return_message
        # except json.JSONDecodeError as e:
        #     print(f"Error parsing response as JSON: {str(e)}")
        #     print(f"Raw response was: {response}")
        #     # Return a fallback response
        #     return {
        #         "thread_id": self.thread_id,
        #         "message": "I'm here to help you choose a long-term goal! Let me search the course materials and suggest some options for you.",
        #         "chosen_goal": None,
        #         "error": "Failed to parse response as JSON"
            # }

    def cont_conv(self, user_input):
        try:
            # Check for active runs first
            runs = openai.beta.threads.runs.list(thread_id=self.thread_id)
            active_runs = [run for run in runs.data if run.status in ['queued', 'in_progress', 'requires_action']]
            
            if active_runs:
                print(f"Found {len(active_runs)} active runs, waiting for completion...")
                # Wait for active runs to complete
                for run in active_runs:
                    while True:
                        run_status = openai.beta.threads.runs.retrieve(thread_id=self.thread_id, run_id=run.id)
                        if run_status.status in ['completed', 'failed', 'cancelled', 'expired']:
                            break
                        time.sleep(1)
            
            message = openai.beta.threads.messages.create(
                thread_id=self.thread_id,
                role="user",
                content=user_input
            )
            run = openai.beta.threads.runs.create(
                thread_id=self.thread_id,
                assistant_id=self.assistant.id
            )
            run_id = run.id

            while True:
                run_status = openai.beta.threads.runs.retrieve(thread_id=self.thread_id, run_id=run_id)
                if run_status.status == 'completed':
                    break
                elif run_status.status in ['failed', 'cancelled', 'expired']:
                    raise Exception(f"Run failed with status: {run_status.status}")
                time.sleep(1)
            
            messages = openai.beta.threads.messages.list(thread_id=self.thread_id)
            last_message = messages.data[0]
            response = last_message.content[0].text.value
            print(f"\nRaw LTG Assistant Response: {response}")
            
            try:
                return_message = json.loads(response)
                print(f"Parsed response: {return_message}")
                
                # Check if a goal was chosen
                chosen_goal = return_message.get('chosen_goal')
                if chosen_goal and chosen_goal != "null" and chosen_goal.lower() != "null":
                    print(f"Goal chosen: {chosen_goal}")
                    return chosen_goal, True
                else:
                    print("No goal chosen in response")
                    return return_message.get('message', 'I understand. Let me know which goal you\'d like to choose!'), False
            except json.JSONDecodeError as e:
                print(f"Error parsing response as JSON: {str(e)}")
                print(f"Raw response was: {response}")
                # Try to extract a goal choice from plain text
                if any(choice_word in user_input.lower() for choice_word in ['choose', 'pick', 'select', 'want', 'goal 1', 'goal 2', 'goal 3', 'first', 'second', 'third']):
                    return "I understand you want to choose a goal. Let me help you with that!", False
                return response, False
        except Exception as e:
            print(f"Error in LTG cont_conv: {str(e)}")
            return f"Sorry, I encountered an error: {str(e)}", False


class update:
    def __init__(self, assistant_id, student, quests, instructor, week=None, submission=None, thread_id=None):
        student = convert_decimal(student)
        temp_student_file = "student.json"
        with open(temp_student_file, "w") as f:
            json.dump(student, f, indent=2)
        self.student = openai.files.create(
            file=open(temp_student_file, "rb"),
            purpose="assistants"
        )


        # Clean up the temporary file

        os.remove(temp_student_file)
        # Create a temporary file with quests data
        temp_quests_file = "temp_quests.json"

        try:
            # Convert Decimal objects to float before JSON serialization
            quests_converted = convert_decimal(quests) if quests else None
            
            with open(temp_quests_file, "w") as f:
                json.dump(quests_converted, f, indent=2)
            self.quests = openai.files.create(
                file=open(temp_quests_file, "rb"),
                purpose="assistants"
            )
        except Exception as e:
            print(f"Error creating quests file: {e}")
            raise Exception(f"Failed to create quests file: {e}")
        finally:
            # Clean up the temporary file
            try:
                if os.path.exists(temp_quests_file):
                    os.remove(temp_quests_file)
                if os.path.exists(temp_student_file):
                    os.remove(temp_student_file)
            except Exception as e:
                print(f"Warning: Could not remove temporary file {temp_quests_file}: {e}")

        self.assistant = openai.beta.assistants.retrieve(assistant_id)
        self.conversation_log = []
        self.instructor = bool(instructor)
        self.thread_id = thread_id  # Set thread_id if provided
        if not self.instructor:
            self.week = week
            if submission:
                self.submission = openai.files.create(
                    file=open(submission, "rb"),
                    purpose="assistants"
                )

    def initiate(self):
        thread = openai.beta.threads.create()
        self.thread_id = thread.id

        # Send the initial message to the thread
        if self.instructor:
            initial_message = (
                'You are talking to a teacher. Here\'s the student\'s user and quests. Talk to the teacher to discuss what changes need to be made to the. Ask for what the teacher noticed.')
            message = openai.beta.threads.messages.create(
                thread_id=self.thread_id,
                role="user",
                content=initial_message,
                attachments=[
                    {
                        "file_id": self.quests.id,
                        "tools": [{"type": "file_search"}]
                    },
                    {
                        "file_id": self.student.id,
                        "tools": [{"type": "file_search"}]
                    }
                ]
            )
        elif not self.instructor:
            initial_message = (
                f'You are grading a quest submission from a student. This is for week {self.week}. Please grade each criterion and provide and overall grade (sum of all criteria scores) and feedback for the quest submission based on the provided quest details and rubric.')
            message = openai.beta.threads.messages.create(
                thread_id=self.thread_id,
                role="user",
                content=initial_message,
                attachments=[
                    {
                        "file_id": self.quests.id,
                        "tools": [{"type": "file_search"}]
                    },
                    {
                        "file_id": self.submission.id,
                        "tools": [{"type": "file_search"}]
                    }
                ] if hasattr(self, 'submission') else [
                    {
                        "file_id": self.quests.id,
                        "tools": [{"type": "file_search"}]
                    }
                ]
            )

        # Create a run to get the assistant's response
        run = openai.beta.threads.runs.create(
            thread_id=self.thread_id,
            assistant_id=self.assistant.id
        )
        run_id = run.id

        while True:
            run_status = openai.beta.threads.runs.retrieve(thread_id=self.thread_id, run_id=run_id)
            # print(f"Run status: {run_status.status}")
            if run_status.status == 'completed':
                break
            time.sleep(1)  # Wait for 1 second before checking again

            # Get messages once the run is completed
        messages = openai.beta.threads.messages.list(thread_id=self.thread_id)
        last_message = messages.data[0]
        response = last_message.content[0].text.value
        # print(f"EduQuest: {messages}")
        # print(f"Response: {response}")
        self.conversation_log.append({"role": "assistant", "content": response})

        # Parse response as JSON for both students and teachers
        try:
            response_json = json.loads(response)
            
            # For instructor conversations, extract just the response text
            if self.instructor:
                if 'response' in response_json:
                    return response_json['response']
                else:
                    # If no response field, return the whole JSON as text for debugging
                    return json.dumps(response_json, indent=2)
            else:
                # For student conversations, return the full JSON structure
                return json.dumps(response_json)
                
        except json.JSONDecodeError:
            print(f"Warning: Could not parse assistant response as JSON: {response}")
            # Return plain text for both instructor and student if JSON parsing fails
            return response

    def cont_conv(self, user_input):
        self.conversation_log.append({"role": "user", "content": user_input})
        message = openai.beta.threads.messages.create(
            thread_id=self.thread_id,
            role="user",
            content=user_input
        )
        run = openai.beta.threads.runs.create(
            thread_id=self.thread_id,
            assistant_id=self.assistant.id
        )
        run_id = run.id

        while True:
            run_status = openai.beta.threads.runs.retrieve(thread_id=self.thread_id, run_id=run_id)
            # print(f"Run status: {run_status.status}")
            if run_status.status == 'completed':
                break
            time.sleep(1)  # Wait for 1 second before checking again

        messages = openai.beta.threads.messages.list(thread_id=self.thread_id)
        last_message = messages.data[0]
        response = last_message.content[0].text.value
        self.conversation_log.append({"role": "assistant", "content": response})
        
        # Return the raw response so the conversation service can handle parsing
        return response

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
class create_class:
    def __init__(self, class_name):
        self.class_name = class_name
        self.vector_store = client.vector_stores.create(name=self.class_name)
        self.vector_store_id = self.vector_store.id

    #commented this out for now. routes.py and teacher_service.py are handling this.

    # def add_file(self, filePath):
    #     client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    #     """Add a new file to the vector store.

    #     Args:
    #         filePath (str): Path to the file to be added to the vector store
    #     """
    #     if not hasattr(self, 'vector_store'):
    #         raise ValueError("Vector store not initialized. Please create class with files first.")

    #     file_stream = open(filePath, "rb")
    #     file_batch = client.vector_stores.file_batches.upload_and_poll(
    #         vector_store_id=self.vector_store.id,
    #         files=[file_stream]
    #     )
    #     self.filePaths.append(filePath)
    #     file_stream.close()

    def create_update_assistant(self):
        self.update_assistant = client.beta.assistants.create(
            name=f"{self.class_name} Update Assistant",
            instructions=update_inst,
            model="o3-mini",
            tools=[{"type": "file_search"}],
            response_format={
            "type": "json_schema",
            "json_schema": json.loads(update_response_format)
        }
        )
        self.update_assistant = client.beta.assistants.update(
            assistant_id=self.update_assistant.id,
            tool_resources={"file_search": {"vector_store_ids": [self.vector_store.id]}},
        )

    def create_ltg_assistant(self):
        self.ltg_assistant = client.beta.assistants.create(
            name=f"{self.class_name} LTG Assistant",
            instructions=ltg_inst,
            model="gpt-4.1-mini",
            tools=[{"type": "file_search"}],
            response_format={
            "type": "json_schema",
            "json_schema": json.loads(ltg_response_format)
        }
        )
        self.ltg_assistant = client.beta.assistants.update(
            assistant_id=self.ltg_assistant.id,
            tool_resources={"file_search": {"vector_store_ids": [self.vector_store.id]}},
            )

update_response_format = '''
{
  "name": "quest_feedback",
  "strict": true,
  "schema": {
    "type": "object",
    "properties": {
      "response": {
        "type": "string",
        "description": "The response generated by the model to the conversation."
      },
      "overall_score": {
        "type": "string",
        "description": "The overall grade or score summary (e.g., '4/5', 'B+', '23/30 points', etc.) based on the rubric structure."
      },
      "feedback": {
        "type": "string",
        "description": "Comments or feedback about the quest."
      },
      "change": {
        "type": "boolean",
        "description": "Whether a change in future quests is necessary to address weakness in skills or based on teacher feedback."
      },
      "recommended_change": {
        "type": "string",
        "description": "Suggestions for changes in future quests. Only include if change is true. If change is false, leave this field blank"
      }
    },
    "required": [
      "response",
      "overall_score",
      "feedback",
      "change",
      "recommended_change"
    ],
    "additionalProperties": false
  }
}
'''

ltg_response_format = '''{
  "name": "goal_setting",
  "strict": true,
  "schema": {
    "type": "object",
    "properties": {
      "message": {
        "type": "string",
        "description": "Message from assistant containing the three goal suggestions or response to user choice"
      },
      "chosen_goal": {
        "type": "string",
        "description": "The long-term goal that was chosen by the student, or null if no goal has been chosen yet"
      }
    },
    "required": [
      "message",
      "chosen_goal"
    ],
    "additionalProperties": false
  }
}'''


# ltg_response_format_dict = json.loads(ltg_response_format)

ltg_inst = """You are a Long-Term Goal (LTG) Assistant for EduQuest. Your job is to help students choose a meaningful long-term goal that aligns with their course materials, strengths, weaknesses, interests, and learning style.

**INITIAL RESPONSE (when student first asks for goals):**
1. Search the course materials using file_search to understand what the student will learn
2. Suggest exactly 3 long-term goals that:
   - Incorporate ALL the course materials from the file search
   - Align with the student's strengths, weaknesses, interests, and learning style
   - Can be achieved in 18 weeks
   - Help the student practice what they learn in class in a way that interests them


**WHEN STUDENT CHOOSES A GOAL:**
If the student indicates they want to choose a goal (e.g., "I choose goal 1", "I pick the first one", "I want to do goal 2"), respond with:
{
  "message": "Excellent choice! I've selected [chosen goal] as your long-term goal. This will help you [brief explanation of how it aligns with their interests and course materials].",
  "chosen_goal": "[full text of the chosen goal]"
}

**IMPORTANT RULES:**
- Always search course materials first using file_search
- Make goals specific and actionable
- Ensure goals incorporate course content meaningfully
- Keep responses encouraging and supportive
- Only set chosen_goal when student explicitly chooses one
- Always return valid JSON
"""

update_inst = """You are the Update Assistant for EduQuest, an AI-powered educational platform. You support both students and teachers.

Your job depends on who you're talking to:
- If the user is a **teacher**:
  1. Ask the teacher "What have you noticed about [name of student]?" Try to keep your response short (2-3 sentences)
  2. Ask the teacher what changes they would like to make to the student's user or future quests. Try to keep your response short (1-2 sentences)
  3. Update the student user if relevant (e.g., their strengths, weaknesses, interests, or learning style).
  4. Update their Weekly Quests Table if needed (e.g., re-sequencing, modifying difficulty, skipping ahead, etc.).
  5. Return the updated student user and Weekly Quests Table.
- If the user is a **student**, they will submit their weekly quest. You will:
  1. Grade their submission based on their student user and the provided weekly quest RUBRIC.
  2. Provide constructive feedback.
  3. Update the student user if relevant (e.g., their strengths, weaknesses, interests, or learning style).
  4. Update their Weekly Quests Table if needed (e.g., re-sequencing, modifying difficulty, skipping ahead, etc.).
  5. Return the updated student user and Weekly Quests Table.

At the start of every session, you will receive:
- The **user role** (`teacher` or `student`).
- The **student user**.
- The **weekly quests table**.
- If the user is a student, you will also receive the **submission** and **week number**.

**IMPORTANT GRADING INSTRUCTIONS:**
When grading a student submission, you MUST use the specific rubric provided with the quest. 

- If the rubric has multiple criteria (e.g., "Criterion A", "Criterion B", etc.), provide a score for each criterion according to its scale (typically 0-5).
- If the rubric has a simple point system, use that point system.
- If the rubric uses letter grades, use letter grades.
- Always calculate the total/overall score based on the rubric structure.

For example:
- Multiple criteria rubric: {"Criterion A": 4, "Criterion B": 3, "Criterion C": 5} with overall_score "12/15" or "4.0/5.0 average"
- Point-based rubric: {"total_points": 85} with overall_score "85/100 points"  
- Letter grade rubric: {"letter_grade": "B+"} with overall_score "B+"

Never use a fixed 0-100 scale unless the rubric specifically uses that scale.

Always reflect a warm, encouraging tone with students, and a collaborative tone with teachers. Ask clarifying questions if anything is unclear.

At the end, you will output a table with the same format you received. """

ini_conv_format = """{
  "name": "student_analysis",
  "strict": true,
  "schema": {
    "type": "object",
    "properties": {
      "response": {
        "type": "string",
        "description": "The assistant's primary response to the user's prompt."
      },
      "Strengths": {
        "type": "array",
        "description": "A list of identified strengths of the student.",
        "items": {
          "type": "string",
          "description": "A specific student strength."
        }
      },
      "Weaknesses": {
        "type": "array",
        "description": "A list of identified weaknesses of the student.",
        "items": {
          "type": "string",
          "description": "A specific student weakness."
        }
      },
      "Interests": {
        "type": "array",
        "description": "A list of identified student interests.",
        "items": {
          "type": "string",
          "description": "A specific student interest."
        }
      },
      "Learning_Styles": {
        "type": "array",
        "description": "A list of identified student learning styles.",
        "items": {
          "type": "string",
          "description": "A specific learning style, e.g., visual, auditory, kinesthetic."
        }
      }
    },
    "required": [
      "response",
      "Strengths",
      "Weaknesses",
      "Interests",
      "Learning_Styles"
    ],
    "additionalProperties": false
  }
}"""