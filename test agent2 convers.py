from EQ_agents import Agent, Runner
import openai
from openai import OpenAI
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Define the agent
convo_agent = Agent(
    name="ChatBot",
    instructions="You are a helpful, casual assistant that can hold a conversation.",
    model="gpt-4o"
)

# Run conversation loop
async def main():
    print("Start chatting with the AI (type 'exit' to quit):")
    while True:
        user_input = input("\nYou: ")
        if user_input.lower() in {"exit", "quit"}:
            break

        # Run agent on input
        response = await Runner.run(convo_agent, user_input)
        print("Assistant:", response)

if __name__ == "__main__":
    asyncio.run(main())