import openai
import time
import os

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()  # Load the .env file
openai.api_key = os.getenv('OPENAI_API_KEY')
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

'''
conversation_log = 
    [{
        'student_id': '', 
        'conversation_log': 
            [{'content': "", 'role': 'assistant'},
            .
            .
            .
            }]
    }] 
'''

def summarize_conversation(conversation_log):
    # Retrieve the summarization assistant
    assistant = openai.beta.assistants.retrieve("asst_IMuSxVprkgtBXH3xLXjMAvtB")
    thread = openai.beta.threads.create()
    thread_id = thread.id


# ----------------------------------Fix Here Later---------------------------
    # Extract the actual conversation list
    chat_data = conversation_log[0]["conversation_log"]

    # Convert each message into a proper format
    formatted_messages = [
        f"{msg['role'].capitalize()}: {msg.get('content', msg.get('message', ''))}"
        for msg in chat_data
    ]

    # Join all messages into a single string
    content = "\n".join(formatted_messages)
# -----------------------------------------------------------------------------

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
    def __init__(self, student, conversation_log=None):
        self.student = student
        self.thread_id = None
        self.assistant = openai.beta.assistants.retrieve("asst_bmsuvfNCaHJYmqTlnT52AzXE")
        self.conversation_log = conversation_log if conversation_log else []

    def initiate(self):
        thread = openai.beta.threads.create()
        initial_message = f"Hello, I'm {self.student.name}, {self.student.age} years old, in {self.student.grade}th grade."
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
            time.sleep(1) # Wait for 1 second before checking again

            # Get messages once the run is completed
        messages = openai.beta.threads.messages.list(thread_id=self.thread_id)
        last_message = messages.data[0]
        response = last_message.content[0].text.value
        # print(f"EduQuest: {messages}")
        # print(f"Response: {response}")
        self.conversation_log.append({"role": "assistant", "content": response})

        print(f'messages: {response}')
        return response

    def cont_conv(self, user_input):
        if user_input.lower() in ["exit", "quit", "stop"]:
            #call summarize
            return "Ending conversation."
            #do we call summary assistant
        else:
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


class update:
    def __init__(self, student, quests):
        self.student = student
        self.quests = quests
        self.assistant = openai.beta.assistants.retrieve("asst_bmsuvfNCaHJYmqTlnT52AzXE")
        self.conversation_log = []

    def initiate(self):
        thread = openai.beta.threads.create()
        initial_message = (f"the student is {self.student.name}, {self.student.age} years old, in {self.student.grade}th grade. "
                          f"Here are their quests: {self.quests}")
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
        if user_input.lower() in ["exit", "quit", "stop"]:
            return "Ending conversation."
            # do we call summary assistant?
        else:
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
