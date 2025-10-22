# OpenAI Integration - Follows blueprint:python_openai pattern
# the newest OpenAI model is "gpt-5" which was released August 7, 2025.
# do not change this unless explicitly requested by the user

import os
import json
from openai import OpenAI

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
openai_client = OpenAI(api_key=OPENAI_API_KEY)

def generate_lesson_plan(subject, grade, board, topic, duration="60 minutes", model="gpt-3.5-turbo"):
    """Generate a detailed lesson plan using AI
    
    Args:
        subject: Subject name
        grade: Grade level
        board: Exam board
        topic: Topic to teach
        duration: Lesson duration
        model: AI model to use (gpt-3.5-turbo for Growth, gpt-4 for Premium)
    """
    prompt = f"""Create a detailed lesson plan for:
    Subject: {subject}
    Grade: {grade}
    Exam Board: {board}
    Topic: {topic}
    Duration: {duration}
    
    Please provide a comprehensive lesson plan in JSON format with the following structure:
    {{
        "title": "lesson title",
        "objectives": ["objective 1", "objective 2"],
        "materials": ["material 1", "material 2"],
        "activities": [
            {{
                "name": "activity name",
                "duration": "time in minutes",
                "description": "detailed description"
            }}
        ],
        "assessment": "assessment method",
        "homework": "homework assignment"
    }}"""
    
    try:
        response = openai_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are an expert teacher creating educational content. Respond only with valid JSON."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content
        if content:
            return json.loads(content)
        else:
            raise Exception("Empty response from OpenAI")
    except Exception as e:
        raise Exception(f"Failed to generate lesson plan: {e}")

def generate_homework(subject, grade, board, topic, question_type, num_questions=5, model="gpt-3.5-turbo"):
    """Generate homework questions using AI
    
    Args:
        model: AI model to use (gpt-3.5-turbo for Growth, gpt-4 for Premium)
    """
    prompt = f"""Create homework questions for:
    Subject: {subject}
    Grade: {grade}
    Exam Board: {board}
    Topic: {topic}
    Question Type: {question_type}
    Number of Questions: {num_questions}
    
    Please provide questions in JSON format with the following structure:
    {{
        "title": "homework title",
        "instructions": "general instructions",
        "questions": [
            {{
                "question_number": 1,
                "question_text": "question content",
                "marks": "number of marks",
                "answer_guidance": "marking scheme or answer guidance"
            }}
        ],
        "total_marks": "total marks for all questions"
    }}"""
    
    try:
        response = openai_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are an expert teacher creating educational assessments. Respond only with valid JSON."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content
        if content:
            return json.loads(content)
        else:
            raise Exception("Empty response from OpenAI")
    except Exception as e:
        raise Exception(f"Failed to generate homework: {e}")

def generate_questions(subject, grade, board, topic, question_type, difficulty="medium", model="gpt-3.5-turbo"):
    """Generate practice questions using AI
    
    Args:
        model: AI model to use (gpt-3.5-turbo for Growth, gpt-4 for Premium)
    """
    prompt = f"""Create practice questions for:
    Subject: {subject}
    Grade: {grade}
    Exam Board: {board}
    Topic: {topic}
    Question Type: {question_type}
    Difficulty: {difficulty}
    
    Please provide questions in JSON format with the following structure:
    {{
        "title": "question set title",
        "difficulty": "{difficulty}",
        "questions": [
            {{
                "question_number": 1,
                "question_text": "question content",
                "options": ["A) option", "B) option", "C) option", "D) option"],
                "correct_answer": "A",
                "explanation": "explanation of correct answer"
            }}
        ]
    }}"""
    
    try:
        response = openai_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are an expert teacher creating educational assessments. Respond only with valid JSON."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content
        if content:
            return json.loads(content)
        else:
            raise Exception("Empty response from OpenAI")
    except Exception as e:
        raise Exception(f"Failed to generate questions: {e}")