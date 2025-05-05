class Quest:
    def __init__(self, week, name, description, skill_cov, skill_mas = None, grade = None):
        self.week = week
        self.name = name
        self.description = description
        self.skill_cov = skill_cov
        self.skill_mas = skill_mas
        self.grade = grade


