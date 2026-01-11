# OpenAI Integration - Follows blueprint:python_openai pattern
# the newest OpenAI model is "gpt-5" which was released August 7, 2025.
# do not change this unless explicitly requested by the user

import os
import json
from openai import OpenAI

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

# Only initialize client if API key is available (prevents crash on startup)
openai_client = None
if OPENAI_API_KEY:
    openai_client = OpenAI(api_key=OPENAI_API_KEY)

def _check_client():
    """Check if OpenAI client is available"""
    if openai_client is None:
        raise Exception("OpenAI API key not configured. Please set the OPENAI_API_KEY environment variable.")

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
    
    _check_client()
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
    
    _check_client()
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
    
    _check_client()
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

def extract_questions_from_paper(file_path, subject, grade, exam_board, paper_type, model="gpt-4"):
    """Extract questions and generate memo from uploaded exam paper using AI with image support
    
    Args:
        file_path: Path to the uploaded exam paper (PDF)
        subject: Subject name
        grade: Grade level  
        exam_board: Exam board name
        paper_type: Type of paper (paper1, paper2, etc)
        model: AI model to use (default gpt-4 for best quality)
        
    Returns:
        dict with:
            - questions_json: Structured questions with marks, images noted
            - memo_json: Complete marking scheme/answers
            - total_questions: Number of questions extracted
            - total_marks: Total marks for the paper
            - question_type: Detected question type (mcq, structured, mixed)
    """
    prompt = f"""You are an expert examiner analyzing a {exam_board} {subject} Grade {grade} exam paper ({paper_type}).

Extract ALL questions from this exam paper and create a comprehensive marking memo.

For each question, identify:
1. Question number and sub-parts (e.g., 1, 1.1, 1.2, 1.2.a)
2. Complete question text
3. Marks allocated
4. Any diagrams/images (note their presence and description)
5. Question type (MCQ, structured, free response, calculation, etc.)

For the memo, provide:
1. Complete answers/model responses
2. Marking criteria and rubrics
3. Common mistakes to watch for
4. Mark allocation breakdown

Return ONLY valid JSON in this EXACT structure:
{{
    "paper_info": {{
        "subject": "{subject}",
        "grade": "{grade}",
        "exam_board": "{exam_board}",
        "total_marks": 100
    }},
    "questions": [
        {{
            "question_number": "1",
            "question_text": "Full question text here",
            "marks": 5,
            "question_type": "structured",
            "has_diagram": false,
            "diagram_description": "",
            "sub_questions": [
                {{
                    "sub_number": "1.1",
                    "sub_text": "Sub-question text",
                    "marks": 2,
                    "has_diagram": false
                }}
            ]
        }}
    ],
    "memo": [
        {{
            "question_number": "1",
            "answer": "Complete answer or marking scheme",
            "marking_points": ["Point 1 (1 mark)", "Point 2 (1 mark)"],
            "common_mistakes": ["Mistake to watch for"],
            "sub_answers": [
                {{
                    "sub_number": "1.1",
                    "answer": "Answer for sub-question",
                    "marking_points": ["Point 1 (1 mark)"]
                }}
            ]
        }}
    ],
    "question_type_summary": "mixed",
    "total_questions": 5,
    "total_marks": 100
}}

NOTE: For diagrams/images, set has_diagram: true and provide a text description in diagram_description. We'll handle image extraction separately."""
    
    _check_client()
    try:
        import PyPDF2
        
        # Extract text from PDF
        pdf_text = ""
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page in pdf_reader.pages:
                pdf_text += page.extract_text() + "\n\n"
        
        # Call OpenAI with extracted text
        response = openai_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are an expert examiner who extracts questions and creates marking memos from exam papers. Respond only with valid JSON."},
                {"role": "user", "content": f"{prompt}\n\nEXAM PAPER TEXT:\n\n{pdf_text[:8000]}"}  # Limit to avoid token limits
            ],
            response_format={"type": "json_object"},
            temperature=0.3
        )
        
        content = response.choices[0].message.content
        if content:
            result = json.loads(content)
            
            # Ensure we have the required fields
            return {
                'questions_json': {
                    'paper_info': result.get('paper_info', {}),
                    'questions': result.get('questions', [])
                },
                'memo_json': {
                    'memo': result.get('memo', [])
                },
                'total_questions': result.get('total_questions', len(result.get('questions', []))),
                'total_marks': result.get('total_marks', result.get('paper_info', {}).get('total_marks', 0)),
                'question_type': result.get('question_type_summary', 'mixed'),
                'ai_model_used': model
            }
        else:
            raise Exception("Empty response from OpenAI")
            
    except PyPDF2.errors.PdfReadError as e:
        raise Exception(f"Failed to read PDF file: {e}")
    except Exception as e:
        raise Exception(f"Failed to extract questions from paper: {e}")
