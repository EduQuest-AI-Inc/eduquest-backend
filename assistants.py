import openai
from openai import OpenAI
import time
import os
import json
from dotenv import load_dotenv
import json

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
        # self.conversation_log = conversation_log if conversation_log else []

    def initiate(self):
        thread = openai.beta.threads.create()
        initial_message = f"Hello, I'm {self.student["first_name"]} {self.student["last_name"]}, in {self.student["grade"]}th grade. My strengths are {self.student["strength"]}, my weaknesses are {self.student["weakness"]}, my interests are {self.student["interest"]}, and my learning style is {self.student["learning_style"]}. Please recommend 3 long-term goals for me."
        print(f"Initial message: {initial_message}")
        print(
            f"Student: {self.student["strength"]}, {self.student["weakness"]}, {self.student["interest"]}, {self.student["learning_style"]}")
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
            # print(f"Run status: {run_status.status}")
            if run_status.status == 'completed':
                break
            time.sleep(1)
        messages = openai.beta.threads.messages.list(thread_id=self.thread_id)
        last_message = messages.data[0]
        response = last_message.content[0].text.value
        return_message = json.loads(response)

        response_dict = json.loads(response)
        response_dict["thread_id"] = self.thread_id

        return response_dict

    def cont_conv(self, user_input):
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
            time.sleep(1)
        messages = openai.beta.threads.messages.list(thread_id=self.thread_id)
        last_message = messages.data[0]
        response = last_message.content[0].text.value
        print(f"\nRaw LTG Assistant Response: {response}")
        
        try:
            return_message = json.loads(response)
            print(f"Parsed response: {return_message}")
            
            # Check if a goal was chosen
            if not return_message.get('chosen_goal'):
                print("No goal chosen in response")
                return return_message.get('message', ''), False
            else:
                print(f"Goal chosen: {return_message['chosen_goal']}")
                return return_message['chosen_goal'], True
        except json.JSONDecodeError as e:
            print(f"Error parsing response as JSON: {str(e)}")
            return response, False


class update:
    def __init__(self, assistant_id, student, quests, instructor, week=None, submission=None):
        self.student = student
        # Create a temporary file with quests data
        temp_quests_file = "temp_quests.json"
        with open(temp_quests_file, "w") as f:
            json.dump(quests, f, indent=2)
        self.quests = openai.files.create(
            file=open(temp_quests_file, "rb"),
            purpose="assistants"
        )
        # Clean up the temporary file
        os.remove(temp_quests_file)

        self.assistant = openai.beta.assistants.retrieve(assistant_id)
        self.conversation_log = []
        self.instructor = bool(instructor)
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
                    }
                ]
            )
        elif not self.instructor:
            initial_message = (
                f'You are grading a quest submission from a student. This is for week {self.week}. Please grade and provide feedback the quest submission based on the provided quest details and rubric')
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
        return response


# class create_class:
#     def __init__(self, class_name, filePaths=None):
#         self.class_name = class_name
#         self.filePaths = list(filePaths)
#         if len(self.filePaths) > 0:
#             self.file_dir = {}
#             self.vector_store = client.vector_stores.create(name=self.class_name)
#             self.file_streams = [open(path, "rb") for path in self.filePaths]
#             self.file_batch = client.vector_stores.file_batches.upload_and_poll(
#                 vector_store_id=self.vector_store.id, files=self.file_streams
#             )

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
        )
        self.ltg_assistant = client.beta.assistants.update(
            assistant_id=self.ltg_assistant.id,
            tool_resources={"file_search": {"vector_store_ids": [self.vector_store.id]}},
        )


ltg_inst = """You will suggest three long-term goals for a student to work on based on the class they are taking and their strengths, weaknesses, interests, and learning style. This long-term goal should help the student to practice the materials learned in class in the field of their interest in a way that suits their learning style. The student should be able to achieve this long-term goal in 18 weeks while incorporating the things they are learning in the class

Note: Most important thing is to incorporate the ALL class materials in the JSON course schedule from the file search in the suggested long-term goal. 

You will only return the three long-term goal suggestions"""

update_inst = """You are the Update Assistant for EduQuest, an AI-powered educational platform. You support both students and teachers.

Your job depends on who you're talking to:
- If the user is a **teacher**:
  1. Ask the teacher "What have you noticed about [name of student]?" Try to keep your response short (2-3 sentences)
  2. Ask the teacher what changes they would like to make to the student's user or future quests. Try to keep your response short (1-2 sentences)
  3. Update the student user if relevant (e.g., their strengths, weaknesses, interests, or learning style).
  4. Update their Weekly Quests Table if needed (e.g., re-sequencing, modifying difficulty, skipping ahead, etc.).
  5. Return the updated student user and Weekly Quests Table.
- If the user is a **student**, they will submit their weekly quest. You will:
  1. Grade their submission based on their student user and the provided weekly quest.
  2. Provide constructive feedback.
  3. Update the student user if relevant (e.g., their strengths, weaknesses, interests, or learning style).
  4. Update their Weekly Quests Table if needed (e.g., re-sequencing, modifying difficulty, skipping ahead, etc.).
  5. Return the updated student user and Weekly Quests Table.

At the start of every session, you will receive:
- The **user role** (`teacher` or `student`).
- The **student user**.
- The **weekly quests table**.
- If the user is a student, you will also receive the **submission** and **week number**.

Always reflect a warm, encouraging tone with students, and a collaborative tone with teachers. Ask clarifying questions if anything is unclear.

At the end, you will output a table with the same format you received. """