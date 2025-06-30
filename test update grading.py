import json

response = """{\n  \"response\": \"I have reviewed your Week 1 quest submission. Your work demonstrates strong understanding of the fundamental concepts, and you have addressed most prompts effectively. Your submission contained a few minor errors and areas for deeper explanation, but overall the structure and presentation are solid. I would suggest continuing to refine your argumentation in future submissions to further bolster your explanations.\",\n  \"grade\": 85,\n  \"feedback\": \"Well done on presenting your ideas clearly; however, pay attention to the minor inaccuracies and consider expanding on certain points as indicated by the rubric. Keep up the good work and continue refining your critical analysis in the next quests.\",\n  \"change\": false,\n  \"recommended_change\": \"No significant changes are recommended at this time; continue with similar approaches while focusing on addressing minor details for improvement.\"\n}"""


loaded = json.loads(response)
print(loaded['feedback'])
print(loaded['grade'])
