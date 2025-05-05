class student_profile:
    def __init__(self, name, age, gender, grade):
        self.name = name
        self.age = age
        self.gender = gender
        self.grade = grade
        self.interests = []
        self.strengths = []
        self.weaknesses = []

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