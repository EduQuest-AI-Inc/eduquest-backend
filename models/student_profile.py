class student_profile:
    def __init__(self, first_name, last_name, age, gender, grade, strength=None, weakness=None, interest=None, learning_style=None, long_term_goal=None):
        self.first_name = first_name
        self.last_name = last_name
        self.age = age
        self.gender = gender
        self.grade = grade
        self.strength = strength
        self.weakness = weakness
        self.interest = interest
        self.learning_style = learning_style
        self.long_term_goal = long_term_goal

    def to_dict(self):
        return {
            "name": self.name,
            "age": self.age,
            "gender": self.gender,
            "grade": self.grade,
            "interests": self.interests,
            "strengths": self.strengths,
            "weaknesses": self.weaknesses
        }