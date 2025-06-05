from canvasapi import Canvas
from bs4 import BeautifulSoup
import json


class Course:
    def __init__(self, course_id, API_URL, API_KEY):
        self.API_URL = API_URL
        self.API_KEY = API_KEY
        self.canvas = Canvas(API_URL, API_KEY)
        self.course = self.canvas.get_course(course_id)
        self.course_id = course_id
        self.module_ids = [module.id for module in self.course.get_modules()]
        self.modules = []
        for module_id in self.module_ids:
            self.modules.append(self.Module(self, module_id))

    class Module:
        def __init__(self, Course, module_id):
            self.course = Course.course
            self.module = self.course.get_module(module_id)
            self.course_id = self.course.id
            self.title = self.module.name
            self.items = []
            self.item_ids = [item.id for item in self.module.get_module_items()]
            for item_id in self.item_ids:
                self.items.append(self.get_item(item_id))

        class Assignment:
            def __init__(self, assignment_id, course):
                self.course = course
                self.cv_assignment = self.course.get_assignment(assignment_id)
                self.title = self.cv_assignment.name
                if self.cv_assignment.description is not None:
                    html_content = self.cv_assignment.description
                    soup = BeautifulSoup(html_content, "html.parser")
                    for tag in soup(["script", "style", "link"]):
                        tag.decompose()
                    self.decription = soup.get_text(separator="\n", strip=True)
                self.due_date = str(self.cv_assignment.due_at_date)

        class Quiz:  # do we want it?
            def __init__(self, quiz_id, course):
                self.course = course
                self.quiz = self.course.get_quiz(quiz_id)
                self.title = self.quiz.title
                # self.due_date = str(self.quiz.due_at_date)
                if self.quiz.description is not None:
                    html_content = self.quiz.description
                    soup = BeautifulSoup(html_content, "html.parser")
                    for tag in soup(["script", "style", "link"]):
                        tag.decompose()
                    self.description = soup.get_text(separator="\n", strip=True)

        class File:
            def __init__(self, file_id, course):
                self.course = course
                self.file = self.course.get_file(file_id)
                self.id = file_id
                self.title = self.file.display_name
                # self.mime_type = self.file.content_type
                self.download_url = self.file.url
                self.content = None
                self.processed_content = None
                self.metadata = {}

        class Page:
            def __init__(self, page_id, course):
                self.course = course
                self.page = self.course.get_page(page_id)
                self.title = self.page.title
                self.body = None
                if self.page.body is not None:
                    html_content = self.page.body
                    soup = BeautifulSoup(html_content, "html.parser")
                    for tag in soup(["script", "style", "link"]):
                        tag.decompose()
                    self.body = soup.get_text(separator="\n", strip=True)

        class Discussion:
            def __init__(self, discussion_id, course):
                self.course = course
                self.discussion = self.course.get_discussion_topic(discussion_id)
                self.title = self.discussion.title
                if self.discussion.message is not None:
                    html_content = self.discussion.message
                    soup = BeautifulSoup(html_content, "html.parser")
                    for tag in soup(["script", "style", "link"]):
                        tag.decompose()
                    self.body = soup.get_text(separator="\n", strip=True)

        def get_item(self, item_id):
            item = self.module.get_module_item(item_id)
            if item.type == 'Assignment':
                item = self.Assignment(item.content_id, self.course)
            elif item.type == 'Quiz':
                item = self.Quiz(item.content_id, self.course)
            elif item.type == 'File':
                item = self.File(item.content_id, self.course)
            elif item.type == 'Page':
                item = self.Page(item.title, self.course)
            elif item.type == 'Discussion':
                item = self.Discussion(item.content_id, self.course)
            else:
                pass

            return item


def course_to_json(course_obj):
    def datetime_handler(obj):
        if hasattr(obj, 'isoformat'):
            return obj.isoformat()
        return 'NA'

    course_dict = {
        "modules": []
    }

    for module in course_obj.modules:
        module_dict = {
            "title": module.title,
            "items": []
        }

        for item in module.items:
            item_dict = {
                "type": item.__class__.__name__,
                "title": getattr(item, 'title', 'NA'),
                "description": getattr(item, 'description', 'NA'),
                "due_date": datetime_handler(getattr(item, 'due_date', 'NA')),
                "download_link": getattr(item, 'download_url', 'NA'),
                "file_type": getattr(item, 'mime_type', 'NA')
            }
            module_dict["items"].append(item_dict)

        course_dict["modules"].append(module_dict)

    return json.dumps(course_dict, indent=2)