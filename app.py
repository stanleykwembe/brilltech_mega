import streamlit as st
import os
import django
from pathlib import Path

# Set up Django
BASE_DIR = Path(__file__).resolve().parent
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_project.settings')

try:
    django.setup()
    from core.models import Subject, Grade, ExamBoard, UserProfile, UploadedDocument, GeneratedAssignment, UsageQuota
    from django.contrib.auth.models import User
except Exception as e:
    st.error(f"Django setup error: {e}")

st.set_page_config(
    page_title="EduTech Freemium Teacher Platform",
    page_icon="📚",
    layout="wide"
)

def main():
    st.title("📚 EduTech Freemium Teacher Platform")
    st.write("Welcome to the MVP for freemium teacher edtech application!")
    
    # Sidebar for navigation
    st.sidebar.title("Navigation")
    page = st.sidebar.selectbox("Choose a page", [
        "Dashboard",
        "Lesson Plans",
        "Homework/Assignments",
        "Question Generator",
        "Document Upload",
        "Subscription"
    ])
    
    if page == "Dashboard":
        show_dashboard()
    elif page == "Lesson Plans":
        show_lesson_plans()
    elif page == "Homework/Assignments":
        show_assignments()
    elif page == "Question Generator":
        show_question_generator()
    elif page == "Document Upload":
        show_document_upload()
    elif page == "Subscription":
        show_subscription()

def show_dashboard():
    st.header("📊 Dashboard")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Lesson Plans Created", "0/5", "Free Tier")
    
    with col2:
        st.metric("Assignments Generated", "0/5", "Free Tier")
    
    with col3:
        st.metric("Documents Uploaded", "0")
    
    st.subheader("Quick Actions")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📝 Create Lesson Plan"):
            st.info("Navigate to Lesson Plans to create new lesson plans")
    
    with col2:
        if st.button("📋 Generate Assignment"):
            st.info("Navigate to Homework/Assignments to generate new assignments")
    
    with col3:
        if st.button("❓ Create Questions"):
            st.info("Navigate to Question Generator to create questions")

def show_lesson_plans():
    st.header("📝 Lesson Plan Management")
    
    tab1, tab2 = st.tabs(["Generate AI Lesson Plan", "Upload Lesson Plan"])
    
    with tab1:
        st.subheader("AI Lesson Plan Generator")
        
        col1, col2 = st.columns(2)
        with col1:
            subject = st.selectbox("Subject", ["Mathematics", "English", "Science", "History"])
            grade = st.selectbox("Grade", ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12"])
        
        with col2:
            topic = st.text_input("Topic")
            exam_board = st.selectbox("Exam Board", ["Cambridge International (CIE)", "Edexcel", "AQA"])
        
        if st.button("Generate Lesson Plan"):
            with st.spinner("Generating AI lesson plan..."):
                st.success("Lesson plan generated successfully! (MVP - AI integration pending)")
                
                # Mock lesson plan structure
                st.subheader("Generated Lesson Plan")
                st.write(f"**Subject:** {subject}")
                st.write(f"**Grade:** {grade}")
                st.write(f"**Topic:** {topic}")
                st.write(f"**Exam Board:** {exam_board}")
                
                st.write("**Objectives:**")
                st.write("- Students will understand the key concepts")
                st.write("- Students will be able to apply knowledge practically")
                
                st.write("**Activities:**")
                st.write("- Introduction and warm-up (10 mins)")
                st.write("- Main lesson content (25 mins)")
                st.write("- Practice activities (10 mins)")
                st.write("- Summary and homework (5 mins)")
    
    with tab2:
        st.subheader("Upload Your Own Lesson Plan")
        uploaded_file = st.file_uploader("Choose a file", type=['pdf', 'docx'])
        
        if uploaded_file is not None:
            st.success("File uploaded successfully! (MVP - file processing pending)")

def show_assignments():
    st.header("📋 Homework & Assignment Management")
    
    tab1, tab2 = st.tabs(["Generate Assignment", "View Assignments"])
    
    with tab1:
        st.subheader("Generate New Assignment")
        
        col1, col2 = st.columns(2)
        with col1:
            title = st.text_input("Assignment Title")
            subject = st.selectbox("Subject", ["Mathematics", "English", "Science", "History"], key="assign_subject")
            grade = st.selectbox("Grade", ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12"], key="assign_grade")
        
        with col2:
            due_date = st.date_input("Due Date")
            exam_board = st.selectbox("Exam Board", ["Cambridge International (CIE)", "Edexcel", "AQA"], key="assign_board")
            instructions = st.text_area("Instructions")
        
        if st.button("Generate Assignment"):
            st.success("Assignment generated successfully!")
            
            # Mock shareable link
            share_link = f"https://example.com/assignment/{title.lower().replace(' ', '-')}"
            st.write(f"**Shareable Link:** {share_link}")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.button("📱 Share on WhatsApp")
            with col2:
                st.button("🏫 Share on Google Classroom")
            with col3:
                st.button("✉️ Share via Email")
    
    with tab2:
        st.subheader("Your Assignments")
        st.info("No assignments created yet. Generate your first assignment!")

def show_question_generator():
    st.header("❓ AI Question Generator")
    
    col1, col2 = st.columns(2)
    
    with col1:
        question_type = st.selectbox("Question Type", [
            "Multiple Choice (MCQ)",
            "Structured/Short Answer",
            "Free Response/Essay",
            "Cambridge-style Structured"
        ])
        
        subject = st.selectbox("Subject", ["Mathematics", "English", "Science", "History"], key="q_subject")
        grade = st.selectbox("Grade", ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12"], key="q_grade")
    
    with col2:
        exam_board = st.selectbox("Exam Board", ["Cambridge International (CIE)", "Edexcel", "AQA"], key="q_board")
        difficulty = st.selectbox("Difficulty", ["Easy", "Medium", "Hard"])
        topic = st.text_input("Specific Topic", key="q_topic")
    
    if st.button("Generate Questions"):
        with st.spinner("Generating questions using AI..."):
            st.success("Questions generated successfully! (MVP - AI integration pending)")
            
            # Mock generated question based on type
            st.subheader("Generated Question")
            
            if question_type == "Multiple Choice (MCQ)":
                st.write(f"**Question:** What is the main concept in {topic}?")
                st.write("A) Option 1")
                st.write("B) Option 2")
                st.write("C) Option 3")
                st.write("D) Option 4")
                st.write("**Answer:** B")
            
            elif question_type == "Cambridge-style Structured":
                st.write(f"**Question:** Analyze the following concept in {topic}:")
                st.write("a) Define the key terms (2 marks)")
                st.write("b) Explain the main principles (4 marks)")
                st.write("c) Evaluate the applications (6 marks)")
            
            else:
                st.write(f"**Question:** Discuss the importance of {topic} in {subject}.")
                st.write("**Answer Guidelines:** Students should mention key concepts, examples, and real-world applications.")

def show_document_upload():
    st.header("📁 Document Upload & Management")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Upload New Document")
        doc_type = st.selectbox("Document Type", [
            "Lesson Plan",
            "Homework",
            "Past Paper",
            "Sample Questions"
        ])
        
        subject = st.selectbox("Subject", ["Mathematics", "English", "Science", "History"], key="doc_subject")
        grade = st.selectbox("Grade", ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12"], key="doc_grade")
        exam_board = st.selectbox("Exam Board", ["Cambridge International (CIE)", "Edexcel", "AQA"], key="doc_board")
        
        uploaded_file = st.file_uploader("Choose a file", type=['pdf', 'docx'], key="doc_upload")
        
        if uploaded_file is not None:
            if st.button("Upload Document"):
                st.success("Document uploaded successfully!")
    
    with col2:
        st.subheader("Filter Documents")
        filter_subject = st.selectbox("Filter by Subject", ["All", "Mathematics", "English", "Science", "History"])
        filter_grade = st.selectbox("Filter by Grade", ["All", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12"])
        filter_board = st.selectbox("Filter by Exam Board", ["All", "Cambridge International (CIE)", "Edexcel", "AQA"])
        
        st.info("No documents uploaded yet.")

def show_subscription():
    st.header("💎 Subscription Management")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Current Plan: Free Tier")
        st.write("**Features:**")
        st.write("✅ 5 lesson plans per subject")
        st.write("✅ 5 homework/assignments per subject")
        st.write("✅ Basic question generation")
        st.write("❌ Unlimited access")
        st.write("❌ Advanced AI features")
        st.write("❌ Priority support")
        
        st.subheader("Usage This Month")
        st.progress(0.0, "Lesson Plans: 0/5 per subject")
        st.progress(0.0, "Assignments: 0/5 per subject")
    
    with col2:
        st.subheader("Upgrade to Premium")
        st.write("**Premium Features:**")
        st.write("✅ Unlimited lesson plans")
        st.write("✅ Unlimited assignments")
        st.write("✅ Advanced AI question generation")
        st.write("✅ Priority support")
        st.write("✅ Export to multiple formats")
        st.write("✅ Advanced analytics")
        
        st.write("**Price:** $29.99/month")
        
        if st.button("Upgrade to Premium"):
            st.info("Payment integration coming soon! (Stripe integration pending)")

if __name__ == "__main__":
    main()