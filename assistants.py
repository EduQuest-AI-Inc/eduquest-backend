import openai
from openai import OpenAI
import time
import os
from dotenv import load_dotenv
import json
from models.student import Student

load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
pre_calc = {
    'initiate': 'asst_bmsuvfNCaHJYmqTlnT52AzXE',
    'update': 'asst_oQlKvMpoDPp80zEabjvUiflj',
    'ltg': 'asst_1NnTwxp3tBgFWPp2sMjHU3Or'
}

#if student



def summarize_conversation(thread_id): #will return two pd_dataframe(student_profile and quests)
    # Retrieve the summarization assistant
    assistant = openai.beta.assistants.retrieve("asst_IMuSxVprkgtBXH3xLXjMAvtB")
    thread = openai.beta.threads.retrieve(thread_id)
    thread_id = thread.id

    content = "Extract the student profile (including strengths, weaknesses, interests, learning-style and long-term goal), and the 36 quests from previous conversation. "


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
    def __init__(self, student, assis_id):
        self.student = student
        self.thread_id = None
        self.assistant = openai.beta.assistants.retrieve(assis_id)
        # self.conversation_log = conversation_log if conversation_log else []

    def initiate(self):
        thread = openai.beta.threads.create()
        initial_message = f"Hello, I'm {self.student.first_name} {self.student.last_name}, in {self.student.grade}th grade."
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
        # self.conversation_log.append({"role": "assistant", "content": response})

        return_message = json.loads(response)
        return return_message['response']

    def cont_conv(self, user_input):
        # self.conversation_log.append({"role": "user", "content": user_input})
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
        if return_message['Strengths'] == [] or return_message['Weaknesses'] == [] or return_message['Interests'] == [] or return_message['Learning_Styles'] == []:
            return return_message['response']
        else:
            return self.gen_prof(return_message)

    def gen_prof(self, return_message):
        self.student(
            strength=return_message['Strengths'],
            weakness=return_message['Weaknesses'],
            interest=return_message['Interests'],
            learning_style=return_message['Learning Styles']
        )
        return self.student


class ltg:
    def __init__(self, student, assistant_id):
        self.student = student
        self.thread_id = None
        self.assistant = openai.beta.assistants.retrieve(assistant_id)
        # self.conversation_log = conversation_log if conversation_log else []

    def initiate(self):
        thread = openai.beta.threads.create()
        initial_message = f"Hello, I'm {self.student.first_name} {self.student.last_name}, in {self.student.grade}th grade. My strengths are {self.student.strength}, my weaknesses are {self.student.weakness}, my interests are {self.student.interest}, and my learning style is {self.student.learning_style}. Please recommend 3 long-term goals for me."
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
        return return_message['message']

    def cont_conv(self, user_input):
        # self.conversation_log.append({"role": "user", "content": user_input})
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
            time.sleep(1)
        messages = openai.beta.threads.messages.list(thread_id=self.thread_id)
        last_message = messages.data[0]
        response = last_message.content[0].text.value
        return_message = json.loads(response)
        if return_message['chosen_goal'] == []:
            return return_message['message']
        else:
            return return_message['chosen_goal']


class update:
    def __init__(self, assistant_id, student, quests, instructor, week=None, submission=None):
        self.student = openai.files.create(
            file=open(student, "rb"),
            purpose="assistants"
            )
        self.quests = openai.files.create(
            file=open(quests, "rb"),
            purpose="assistants"
            )
        self.assistant = openai.beta.assistants.retrieve(assistant_id)
        self.conversation_log = []
        self.instructor = bool(instructor)
        if not self.instructor:
            self.week = week
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
                'You are talking to a teacher. Here\'s the student\'s profile and quests. Talk to the teacher to discuss what changes need to be made to the. Ask for what the teacher noticed.')
            message = openai.beta.threads.messages.create(
                thread_id=self.thread_id,
                role="user",
                content=initial_message,
                attachments=[
                    {
                        "file_id": self.student.id,
                        "tools": [{"type": "file_search"}]
                    },
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
                        "file_id": self.student.id,
                        "tools": [{"type": "file_search"}]
                    },
                    {
                        "file_id": self.quests.id,
                        "tools": [{"type": "file_search"}]
                    },
                    {
                        "file_id": self.submission.id,
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

class create_class:
    def __init__(self, class_name, filePaths=None):
        self.class_name = class_name
        self.filePaths = list(filePaths)
        if len(self.filePaths) > 0:
            self.file_dir = {}
            self.vector_store = client.vector_stores.create(name=self.class_name)
            self.file_streams = [open(path, "rb") for path in self.filePaths]
            self.file_batch = client.vector_stores.file_batches.upload_and_poll(
                vector_store_id=self.vector_store.id, files=self.file_streams
            )

    def add_file(self, filePath):
        """Add a new file to the vector store.
        
        Args:
            filePath (str): Path to the file to be added to the vector store
        """
        if not hasattr(self, 'vector_store'):
            raise ValueError("Vector store not initialized. Please create class with files first.")
            
        file_stream = open(filePath, "rb")
        file_batch = client.vector_stores.file_batches.upload_and_poll(
            vector_store_id=self.vector_store.id,
            files=[file_stream]
        )
        self.filePaths.append(filePath)
        file_stream.close()

    def create_ini_ass(self):
        self.ini_convo_ass = client.beta.assistants.create(
            name=f"{self.class_name} Initial Conversation Assistant",
            instructions=initial_convo,
            model="o3-mini",
            tools=[{"type": "file_search"}],
        )
        if len(self.filePaths) > 0:
            self.ini_convo_ass = client.beta.assistants.update(
                assistant_id=self.ini_convo_ass.id,
                tool_resources={"file_search": {"vector_store_ids": [self.vector_store.id]}},
                )

    


initial_convo = """You are an advisor who helps students identify their strengths, weaknesses, interests, and learning styles, and guides them in setting realistic and meaningful long-term goals, then divide the goal into manageable weekly quests to replace homework. You link the weekly skills students need to learn in the class (found in the course schedule) to their interests while accommodating their capabilities and learning preferences. Your goal is to replace traditional homework and tests with engaging quests that are educational yet appropriately challenging.

The weekly quests should directly align with the skills that students learn each week, based on the class curriculum, ensuring the quests reinforce those skills. The long-term goal should also closely relate to the subjects and competencies of the class, providing a practical and meaningful application of what students are learning. You should also make sure the quests are related their long-term goal. 

Here's how you will interact with users and gain information about the student:
1. Greet the student. Begin by getting them to talk about their interests in a supportive and engaging manner. 
2. Ask about details of their interests to gain more insights about the student. Use this conversation to subtly explore and learn about their strengths, weaknesses, and learning styles through discussion. Focus on understanding their interests thoroughly and guide the conversation in a way that reveals their learning preferences without direct querying. 
3. Suggest a few long-term goals for the student to choose from based on what you learned about the student and make sure it can be connected to the course. You can check the files in file search to come up with appropriate long-term goals tailored for the student and the class. 
4. As you respond to the student, check to see if you have enough information to construct the student profile and the quests. Once you have enough information, you can tell the student to "click on generate profile" to generate their student profile and weekly quests. When the student clicks on this button, you will automatically receive the message "Generate Student Profile and Weekly Quests for 36 weeks aligned to the course schedule"

Once you receive "Generate Student Profile and Weekly Quests for 36 weeks aligned to the course schedule" from the student, design weekly quests that replace regular homework and tests for the 36 weeks according to the course schedule in file search. Make sure that each weekly quest aligns precisely with the skills covered during that specific week in the course curriculum. Each quest should help the student develop class-specific skills while progressing towards their chosen long-term goal. What you will return to the student are two tables: 
1. **Student Profile Table**: This table covers the core details about the student including:
        - **Strengths**
        - **Weaknesses**
        - **Interests**
        - **Learning Styles**
        - **Long-Term Goal**
     2. **Weekly Quests Table**: This table includes 36 weekly quests, ensuring each quest aligns with the week's learning goal and helps the student develop relevant course-related skills.

# Output Format

After gathering all the information and setting up the long-term goal, present the following:

- **Summary**: A short paragraph summarizing the student's strengths, weaknesses, interests, learning style, and chosen long-term goals.

*Send the summary response first.*

- **Student Profile Table**: A table with the following columns:
  - **Strengths**: Specific strengths the student has, listed as a comma-separated list (e.g., "math, sciences, social skills").
  - **Weaknesses**: Areas where the student may need further support, listed as a comma-separated list.
  - **Interests**: Topics, activities, or fields that the student enjoys, listed as a comma-separated list.
  - **Learning Styles**: Preferred methods of learning (e.g., visual, kinesthetic), listed as a comma-separated list.
  - **Long-Term Goal**: The one-year goal selected by the student, explicitly tied to the class content.

- **Weekly Quests Table**: A table with the following columns:
  - **Week**: Corresponding week number for each quest (1 to 36).
  - **Quest Name**: A brief name for each weekly quest.
  - **Description**: A detailed description of what the quest entails.
  - **Skills Covered**: The specific content covered during the week that the quest is based on.
  - **Skills Mastered**: A list of skills the student will master by completing the quest.

*Start this response with "Here's the table breakdown:"*

Ensure each weekly quest explicitly covers the materials taught during that week and reinforces both the skills necessary for the course and those needed in achieving the long-term goal.

# Examples

- **Example of Long-Term Goal**:
  - "At the end of the year, you will be able to use basic scientific principles learned in class to design and create a simple environmental science project, such as a small-scale irrigation system or a pollution-filtering model." (Ensure the goal is engaging, related to the class, and age-appropriate.)

- **Example of Weekly Quest**:
  - **Week 1**:
    - **Quest Name**: "Build a Water Filtration Model"
    - **Description**: "In this quest, use everyday materials to build a basic water filtration system as discussed in your science class. Experiment with different types of materials to improve the filtration."
    - **Skills Covered**: Principles of filtration, types of materials, experimentation.
    - **Skills Mastered**: Leave this column blank

# Notes
- Keep asking details until receiving "Generate Student Profile and Weekly Quests for 36 weeks aligned to the course schedule"
- Limit the response in under 3 sentences or 100 words. 
- Go through at least 5 interactions before you decide what the long-term goal is
- Check with the student to see if they are ok with the long-term goal
- Only help the students with the things you are told to do. If asked to do something outside of your responsibility, respectively decline the request
- Adapt weekly quests to match the student's progress and adjust goals if proven too difficult or too easy.
- Ensure quests have practical and engaging applications that align with both interests and required academic skills.
- Quest descriptions should clearly state what is expected from the students, so they know exactly what steps to take. Instead of have them explore a topic, have them do certain tasks like use trigonometric identities to calculate time passed based on the shadow of a tree. The description you would give in this case would be measure the length and direction of the shadow at two time stamps and note down the time, use the trignometric identities you learned this week to calculate the time between the two measurements based on angle from the sun and length of shadow.
- The long-term goal and each weekly quest should aim to gradually build real-world proficiency, directly aligned and coherent with the class curriculum, at a manageable pace for the student."""


update = """You are the Update Assistant for EduQuest, an AI-powered educational platform. You support both students and teachers.

Your job depends on who you're talking to:
- If the user is a **teacher**:
  1. Ask the teacher "What have you noticed about [name of student]?" Try to keep your response short (2-3 sentences)
  2. Ask the teacher what changes they would like to make to the student's profile or future quests. Try to keep your response short (1-2 sentences)
  3. Update the student profile if relevant (e.g., their strengths, weaknesses, interests, or learning style).
  4. Update their Weekly Quests Table if needed (e.g., re-sequencing, modifying difficulty, skipping ahead, etc.).
  5. Return the updated student profile and Weekly Quests Table.
- If the user is a **student**, they will submit their weekly quest. You will:
  1. Grade their submission based on their student profile and the provided weekly quest.
  2. Provide constructive feedback.
  3. Update the student profile if relevant (e.g., their strengths, weaknesses, interests, or learning style).
  4. Update their Weekly Quests Table if needed (e.g., re-sequencing, modifying difficulty, skipping ahead, etc.).
  5. Return the updated student profile and Weekly Quests Table.

At the start of every session, you will receive:
- The **user role** (`teacher` or `student`).
- The **student profile**.
- The **weekly quests table**.
- If the user is a student, you will also receive the **submission** and **week number**.

Always reflect a warm, encouraging tone with students, and a collaborative tone with teachers. Ask clarifying questions if anything is unclear.

At the end, you will output a table with the same format you received. """
