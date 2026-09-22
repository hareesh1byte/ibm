"""
db.py — Data layer for the College Portal.

This is a Python translation of the original Node.js `db.js`. It keeps the
same resilient in-memory dataset (mirroring the PostgreSQL schema/seed data)
and exposes helper functions used by both the JSON API and the
server-rendered pages.
"""

import os
import time
from datetime import datetime
from copy import deepcopy

try:
    import psycopg2
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False

# ---------------------------------------------------------------------------
# Config (mirrors dbConfig in db.js)
# ---------------------------------------------------------------------------
DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": int(os.environ.get("DB_PORT", "5432")),
    "dbname": os.environ.get("DB_NAME", "college_portal"),
    "user": os.environ.get("DB_USER", "postgres"),
    "password": os.environ.get("DB_PASSWORD", "postgres_secure_pass"),
    "connect_timeout": 2,
}

_is_pg_connected = False
_db_mode = "Checking..."
_start_time = time.time()

# ---------------------------------------------------------------------------
# In-memory seed data (translated 1:1 from the JS memoryStore)
# ---------------------------------------------------------------------------
STORE = {
    "users": [
        {"id": 1, "username": "student", "email": "alex.chen@apex.edu", "password": "password123",
         "role": "student", "full_name": "Alex Chen",
         "avatar_url": "https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=256&q=80"},
        {"id": 4, "username": "sophia", "email": "sophia.m@apex.edu", "password": "password123",
         "role": "student", "full_name": "Sophia Martinez",
         "avatar_url": "https://images.unsplash.com/photo-1494790108377-be9c29b29330?auto=format&fit=crop&w=256&q=80"},
        {"id": 5, "username": "david", "email": "david.k@apex.edu", "password": "password123",
         "role": "student", "full_name": "David Kim",
         "avatar_url": "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?auto=format&fit=crop&w=256&q=80"},
        {"id": 6, "username": "aisha", "email": "aisha.p@apex.edu", "password": "password123",
         "role": "student", "full_name": "Aisha Patel",
         "avatar_url": "https://images.unsplash.com/photo-1517841905240-472988babdf9?auto=format&fit=crop&w=256&q=80"},
        {"id": 7, "username": "lucas", "email": "lucas.s@apex.edu", "password": "password123",
         "role": "student", "full_name": "Lucas Silva",
         "avatar_url": "https://images.unsplash.com/photo-1522075469751-3a6694fb2f61?auto=format&fit=crop&w=256&q=80"},
        {"id": 2, "username": "faculty", "email": "robert.vance@apex.edu", "password": "password123",
         "role": "faculty", "full_name": "Dr. Robert Vance",
         "avatar_url": "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?auto=format&fit=crop&w=256&q=80"},
        {"id": 8, "username": "anita", "email": "anita.s@apex.edu", "password": "password123",
         "role": "faculty", "full_name": "Prof. Anita Sharma",
         "avatar_url": "https://images.unsplash.com/photo-1573497019940-1c28c88b4f3e?auto=format&fit=crop&w=256&q=80"},
        {"id": 9, "username": "kenneth", "email": "kenneth.c@apex.edu", "password": "password123",
         "role": "faculty", "full_name": "Dr. Kenneth Cole",
         "avatar_url": "https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?auto=format&fit=crop&w=256&q=80"},
        {"id": 3, "username": "admin", "email": "admin@apex.edu", "password": "password123",
         "role": "admin", "full_name": "Dr. Elena Rostova",
         "avatar_url": "https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?auto=format&fit=crop&w=256&q=80"},
    ],
    "students": [
        {"id": 1, "user_id": 1, "full_name": "Alex Chen", "email": "alex.chen@apex.edu",
         "roll_number": "APX-2022-CS-084", "department": "Computer Science & Cloud Computing",
         "semester": 6, "batch_year": "2022-2026", "overall_attendance": 88.4, "cgpa": 8.92,
         "mentor_name": "Dr. Robert Vance",
         "avatar_url": "https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=256&q=80",
         "status": "Active"},
        {"id": 2, "user_id": 4, "full_name": "Sophia Martinez", "email": "sophia.m@apex.edu",
         "roll_number": "APX-2022-CS-091", "department": "Computer Science & Cloud Computing",
         "semester": 6, "batch_year": "2022-2026", "overall_attendance": 94.0, "cgpa": 9.35,
         "mentor_name": "Dr. Robert Vance",
         "avatar_url": "https://images.unsplash.com/photo-1494790108377-be9c29b29330?auto=format&fit=crop&w=256&q=80",
         "status": "Active"},
        {"id": 3, "user_id": 5, "full_name": "David Kim", "email": "david.k@apex.edu",
         "roll_number": "APX-2022-CS-104", "department": "Artificial Intelligence & Data Science",
         "semester": 6, "batch_year": "2022-2026", "overall_attendance": 82.5, "cgpa": 8.41,
         "mentor_name": "Prof. Anita Sharma",
         "avatar_url": "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?auto=format&fit=crop&w=256&q=80",
         "status": "Active"},
        {"id": 4, "user_id": 6, "full_name": "Aisha Patel", "email": "aisha.p@apex.edu",
         "roll_number": "APX-2023-CS-022", "department": "Computer Science & Cloud Computing",
         "semester": 4, "batch_year": "2023-2027", "overall_attendance": 91.2, "cgpa": 8.78,
         "mentor_name": "Dr. Kenneth Cole",
         "avatar_url": "https://images.unsplash.com/photo-1517841905240-472988babdf9?auto=format&fit=crop&w=256&q=80",
         "status": "Active"},
        {"id": 5, "user_id": 7, "full_name": "Lucas Silva", "email": "lucas.s@apex.edu",
         "roll_number": "APX-2022-ECE-044", "department": "Electronics & Communication",
         "semester": 6, "batch_year": "2022-2026", "overall_attendance": 76.0, "cgpa": 7.65,
         "mentor_name": "Dr. Sarah Connor",
         "avatar_url": "https://images.unsplash.com/photo-1522075469751-3a6694fb2f61?auto=format&fit=crop&w=256&q=80",
         "status": "Active"},
    ],
    "faculty": [
        {"id": 1, "user_id": 2, "full_name": "Dr. Robert Vance", "email": "robert.vance@apex.edu",
         "employee_id": "FAC-CS-109", "department": "Computer Science & Cloud Computing",
         "designation": "Professor & Cloud Lead",
         "specialization": "Distributed Systems & Docker Containerization",
         "cabin_location": "IBM Center of Excellence, Room 402",
         "avatar_url": "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?auto=format&fit=crop&w=256&q=80",
         "courses": ["CS601", "CS604"], "courses_count": 2},
        {"id": 2, "user_id": 8, "full_name": "Prof. Anita Sharma", "email": "anita.s@apex.edu",
         "employee_id": "FAC-CS-114", "department": "Computer Science & Engineering",
         "designation": "Associate Professor",
         "specialization": "Full Stack Frameworks & Reactive Systems",
         "cabin_location": "Block C, Room 310",
         "avatar_url": "https://images.unsplash.com/photo-1573497019940-1c28c88b4f3e?auto=format&fit=crop&w=256&q=80",
         "courses": ["CS602"], "courses_count": 1},
        {"id": 3, "user_id": 9, "full_name": "Dr. Kenneth Cole", "email": "kenneth.c@apex.edu",
         "employee_id": "FAC-CS-098", "department": "Computer Science",
         "designation": "Assistant Professor",
         "specialization": "Database Internals & Storage Sharding",
         "cabin_location": "Block B, Room 204",
         "avatar_url": "https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?auto=format&fit=crop&w=256&q=80",
         "courses": ["CS603"], "courses_count": 1},
    ],
    "courses": [
        {"id": 1, "course_code": "CS601", "course_name": "Cloud Computing & Microservices",
         "department": "Computer Science", "credits": 4, "instructor": "Dr. Robert Vance", "semester": 6,
         "description": "Design, containerization, and orchestration of cloud applications using Docker, Kubernetes, and IBM Cloud services.",
         "thumbnail": "https://images.unsplash.com/photo-1451187580459-43490279c0fa?auto=format&fit=crop&w=400&q=80",
         "enrolled": 72},
        {"id": 2, "course_code": "CS602", "course_name": "Full-Stack Web Architectures",
         "department": "Computer Science", "credits": 4, "instructor": "Prof. Anita Sharma", "semester": 6,
         "description": "Modern web frameworks, REST APIs, asynchronous messaging, and container deployment pipelines.",
         "thumbnail": "https://images.unsplash.com/photo-1555066931-4365d14bab8c?auto=format&fit=crop&w=400&q=80",
         "enrolled": 68},
        {"id": 3, "course_code": "CS603", "course_name": "Database Internals & Distributed Storage",
         "department": "Computer Science", "credits": 3, "instructor": "Dr. Kenneth Cole", "semester": 6,
         "description": "ACID transactions, PostgreSQL indexing, distributed clustering, and volume persistence in Docker.",
         "thumbnail": "https://images.unsplash.com/photo-1544383835-bda2bc66a55d?auto=format&fit=crop&w=400&q=80",
         "enrolled": 65},
        {"id": 4, "course_code": "CS604", "course_name": "Container Security & DevSecOps",
         "department": "Computer Science", "credits": 3, "instructor": "Dr. Robert Vance", "semester": 6,
         "description": "Image vulnerability scanning, rootless containers, RBAC policies, and CI/CD security gating.",
         "thumbnail": "https://images.unsplash.com/photo-1563986768609-322da13575f3?auto=format&fit=crop&w=400&q=80",
         "enrolled": 58},
        {"id": 5, "course_code": "CS605", "course_name": "Artificial Intelligence & Neural Systems",
         "department": "AI & Data Science", "credits": 4, "instructor": "Dr. Sarah Connor", "semester": 6,
         "description": "Deep learning neural networks, computer vision, and deploying scalable inference containers.",
         "thumbnail": "https://images.unsplash.com/photo-1677442136019-21780ecad995?auto=format&fit=crop&w=400&q=80",
         "enrolled": 80},
    ],
    "attendance": [
        {"student_id": 1, "id": 1, "course_id": 1, "course_code": "CS601", "course_name": "Cloud Computing & Microservices", "total_classes": 42, "attended_classes": 39, "percentage": 92.8},
        {"student_id": 1, "id": 2, "course_id": 2, "course_code": "CS602", "course_name": "Full-Stack Web Architectures", "total_classes": 40, "attended_classes": 36, "percentage": 90.0},
        {"student_id": 1, "id": 3, "course_id": 3, "course_code": "CS603", "course_name": "Database Internals & Distributed Storage", "total_classes": 38, "attended_classes": 33, "percentage": 86.8},
        {"student_id": 1, "id": 4, "course_id": 4, "course_code": "CS604", "course_name": "Container Security & DevSecOps", "total_classes": 36, "attended_classes": 31, "percentage": 86.1},
        {"student_id": 1, "id": 5, "course_id": 5, "course_code": "CS605", "course_name": "Artificial Intelligence & Neural Systems", "total_classes": 40, "attended_classes": 34, "percentage": 85.0},
        {"student_id": 2, "id": 6, "course_id": 1, "course_code": "CS601", "course_name": "Cloud Computing & Microservices", "total_classes": 42, "attended_classes": 41, "percentage": 97.6},
        {"student_id": 2, "id": 7, "course_id": 2, "course_code": "CS602", "course_name": "Full-Stack Web Architectures", "total_classes": 40, "attended_classes": 38, "percentage": 95.0},
        {"student_id": 2, "id": 8, "course_id": 3, "course_code": "CS603", "course_name": "Database Internals & Distributed Storage", "total_classes": 38, "attended_classes": 36, "percentage": 94.7},
        {"student_id": 3, "id": 9, "course_id": 5, "course_code": "CS605", "course_name": "Artificial Intelligence & Neural Systems", "total_classes": 40, "attended_classes": 35, "percentage": 87.5},
        {"student_id": 3, "id": 10, "course_id": 1, "course_code": "CS601", "course_name": "Cloud Computing & Microservices", "total_classes": 42, "attended_classes": 33, "percentage": 78.5},
        {"student_id": 4, "id": 11, "course_id": 2, "course_code": "CS602", "course_name": "Full-Stack Web Architectures", "total_classes": 40, "attended_classes": 37, "percentage": 92.5},
        {"student_id": 4, "id": 12, "course_id": 3, "course_code": "CS603", "course_name": "Database Internals", "total_classes": 38, "attended_classes": 34, "percentage": 89.5},
        {"student_id": 5, "id": 13, "course_id": 4, "course_code": "CS604", "course_name": "Container Security & DevSecOps", "total_classes": 36, "attended_classes": 27, "percentage": 75.0},
        {"student_id": 5, "id": 14, "course_id": 1, "course_code": "CS601", "course_name": "Cloud Computing & Microservices", "total_classes": 42, "attended_classes": 32, "percentage": 76.2},
    ],
    "marks": [
        {"student_id": 1, "id": 1, "course_code": "CS601", "course_name": "Cloud Computing & Microservices", "credits": 4, "internal": 29.0, "midterm": 48.0, "assignment": 19.5, "total": 96.5, "grade": "A+"},
        {"student_id": 1, "id": 2, "course_code": "CS602", "course_name": "Full-Stack Web Architectures", "credits": 4, "internal": 27.5, "midterm": 44.0, "assignment": 18.0, "total": 89.5, "grade": "A"},
        {"student_id": 1, "id": 3, "course_code": "CS603", "course_name": "Database Internals & Distributed Storage", "credits": 3, "internal": 28.0, "midterm": 46.5, "assignment": 19.0, "total": 93.5, "grade": "A+"},
        {"student_id": 1, "id": 4, "course_code": "CS604", "course_name": "Container Security & DevSecOps", "credits": 3, "internal": 26.0, "midterm": 43.0, "assignment": 17.5, "total": 86.5, "grade": "A"},
        {"student_id": 1, "id": 5, "course_code": "CS605", "course_name": "Artificial Intelligence & Neural Systems", "credits": 4, "internal": 28.5, "midterm": 45.0, "assignment": 18.5, "total": 92.0, "grade": "A+"},
        {"student_id": 2, "id": 6, "course_code": "CS601", "course_name": "Cloud Computing & Microservices", "credits": 4, "internal": 30.0, "midterm": 49.0, "assignment": 20.0, "total": 99.0, "grade": "A+"},
        {"student_id": 2, "id": 7, "course_code": "CS602", "course_name": "Full-Stack Web Architectures", "credits": 4, "internal": 29.0, "midterm": 48.0, "assignment": 19.0, "total": 96.0, "grade": "A+"},
        {"student_id": 2, "id": 8, "course_code": "CS603", "course_name": "Database Internals & Distributed Storage", "credits": 3, "internal": 28.5, "midterm": 47.0, "assignment": 19.5, "total": 95.0, "grade": "A+"},
        {"student_id": 3, "id": 9, "course_code": "CS605", "course_name": "Artificial Intelligence & Neural Systems", "credits": 4, "internal": 27.0, "midterm": 42.0, "assignment": 17.0, "total": 86.0, "grade": "A"},
        {"student_id": 3, "id": 10, "course_code": "CS601", "course_name": "Cloud Computing & Microservices", "credits": 4, "internal": 25.0, "midterm": 41.0, "assignment": 16.5, "total": 82.5, "grade": "B"},
        {"student_id": 4, "id": 11, "course_code": "CS602", "course_name": "Full-Stack Web Architectures", "credits": 4, "internal": 28.0, "midterm": 45.0, "assignment": 18.0, "total": 91.0, "grade": "A+"},
        {"student_id": 4, "id": 12, "course_code": "CS603", "course_name": "Database Internals", "credits": 3, "internal": 26.5, "midterm": 42.5, "assignment": 17.0, "total": 86.0, "grade": "A"},
        {"student_id": 5, "id": 13, "course_code": "CS604", "course_name": "Container Security & DevSecOps", "credits": 3, "internal": 24.0, "midterm": 38.0, "assignment": 15.0, "total": 77.0, "grade": "B"},
        {"student_id": 5, "id": 14, "course_code": "CS601", "course_name": "Cloud Computing & Microservices", "credits": 4, "internal": 23.5, "midterm": 37.5, "assignment": 16.0, "total": 77.0, "grade": "B"},
    ],
    "timetable": [
        {"id": 1, "day": "Monday", "time": "09:00 AM - 10:30 AM", "code": "CS601", "subject": "Cloud Computing & Microservices", "room": "Lab 4 (IBM Suite)", "instructor": "Dr. Robert Vance"},
        {"id": 2, "day": "Monday", "time": "10:45 AM - 12:15 PM", "code": "CS602", "subject": "Full-Stack Web Architectures", "room": "Auditorium 2", "instructor": "Prof. Anita Sharma"},
        {"id": 3, "day": "Tuesday", "time": "09:00 AM - 10:30 AM", "code": "CS603", "subject": "Database Internals", "room": "Lecture Hall 102", "instructor": "Dr. Kenneth Cole"},
        {"id": 4, "day": "Tuesday", "time": "11:00 AM - 12:30 PM", "code": "CS604", "subject": "Container Security & DevSecOps", "room": "Cyber Lab 1", "instructor": "Dr. Robert Vance"},
        {"id": 5, "day": "Wednesday", "time": "09:00 AM - 11:00 AM", "code": "CS601", "subject": "Docker Hands-on Practicum", "room": "Cloud Lab 3", "instructor": "Dr. Robert Vance"},
        {"id": 6, "day": "Thursday", "time": "10:00 AM - 11:30 AM", "code": "CS605", "subject": "AI & Neural Systems", "room": "AI Research Lab", "instructor": "Dr. Sarah Connor"},
        {"id": 7, "day": "Friday", "time": "02:00 PM - 04:00 PM", "code": "CS602", "subject": "Full-Stack Project Mentoring", "room": "Innovation Center", "instructor": "Prof. Anita Sharma"},
    ],
    "assignments": [
        {"id": 1, "student_id": 1, "course_code": "CS601", "title": "Lab 3: Dockerizing Multi-Tier Node & PostgreSQL App", "due_date": "2026-09-18", "max_score": 100, "score": 98, "status": "Submitted", "description": "Write a Dockerfile and docker-compose.yml to spin up Express, static frontend, and PostgreSQL with volume persistence."},
        {"id": 2, "student_id": 1, "course_code": "CS602", "title": "Project Milestone 2: REST API with Token Auth", "due_date": "2026-09-24", "max_score": 50, "score": None, "status": "Pending", "description": "Implement role-based middleware for student, faculty, and admin roles with error handling."},
        {"id": 3, "student_id": 1, "course_code": "CS604", "title": "Security Audit: Rootless Container Gating", "due_date": "2026-09-30", "max_score": 50, "score": None, "status": "Pending", "description": "Scan images with Trivy and patch CVEs in alpine base layers."},
        {"id": 4, "student_id": 1, "course_code": "CS603", "title": "Query Optimization & Indexing in PostgreSQL", "due_date": "2026-10-05", "max_score": 50, "score": None, "status": "Pending", "description": "Analyze EXPLAIN ANALYZE traces on high-throughput university registration transactions."},
    ],
    "exams": [
        {"id": 1, "course_code": "CS601", "subject": "Cloud Computing & Microservices", "date": "Oct 12, 2026", "time": "10:00 AM - 01:00 PM", "hall": "Examination Hall A, Seat 42", "status": "Upcoming"},
        {"id": 2, "course_code": "CS602", "subject": "Full-Stack Web Architectures", "date": "Oct 15, 2026", "time": "10:00 AM - 01:00 PM", "hall": "Examination Hall B, Seat 18", "status": "Upcoming"},
        {"id": 3, "course_code": "CS603", "subject": "Database Internals & Distributed Storage", "date": "Oct 19, 2026", "time": "10:00 AM - 01:00 PM", "hall": "Examination Hall A, Seat 42", "status": "Upcoming"},
        {"id": 4, "course_code": "CS604", "subject": "Container Security & DevSecOps", "date": "Oct 22, 2026", "time": "10:00 AM - 01:00 PM", "hall": "Cyber Center, Seat 11", "status": "Upcoming"},
    ],
    "events": [
        {"id": 1, "title": "IBM Cloud & Container Hackathon 2026", "category": "Hackathon", "date_string": "September 22, 2026", "venue": "Main Auditorium & Virtual", "description": "A 36-hour sprint where student teams design, containerize, and deploy cloud-native solutions on IBM Cloud infrastructure.", "image_url": "https://images.unsplash.com/photo-1517245386807-bb43f82c33c4?auto=format&fit=crop&w=600&q=80", "registration_count": 142, "registered": False},
        {"id": 2, "title": "DevOps & Docker Orchestration Summit", "category": "Technical", "date_string": "September 28, 2026", "venue": "Seminar Hall B, Block 4", "description": "Hands-on keynote by IBM Senior Engineers on Kubernetes, container security, and zero-downtime rolling updates.", "image_url": "https://images.unsplash.com/photo-1531482615713-2afd69097998?auto=format&fit=crop&w=600&q=80", "registration_count": 98, "registered": True},
        {"id": 3, "title": "Annual Technical Symposium: InnovateX", "category": "Technical", "date_string": "October 05, 2026", "venue": "Campus Convention Center", "description": "Inter-collegiate paper presentations, coding sprints, AI model showcases, and robotics competitions.", "image_url": "https://images.unsplash.com/photo-1540575467063-178a50c2df87?auto=format&fit=crop&w=600&q=80", "registration_count": 270, "registered": False},
        {"id": 4, "title": "Campus Placement & Career Fair 2026", "category": "Placement", "date_string": "October 14, 2026", "venue": "Placement Arena, Ground Floor", "description": "Over 40 top technology employers including IBM, Red Hat, and global IT consultancies recruiting final year students.", "image_url": "https://images.unsplash.com/photo-1521737604893-d14cc237f11d?auto=format&fit=crop&w=600&q=80", "registration_count": 315, "registered": True},
    ],
    "announcements": [
        {"id": 1, "title": "End-Semester Examination Schedule Published", "category": "Exams", "content": "The timetable for 6th-semester final examinations has been finalized. Hall tickets will be downloadable from your student dashboard starting next Monday.", "priority": "Urgent", "date_posted": "September 08, 2026", "author": "Controller of Examinations"},
        {"id": 2, "title": "IBM Campus Hiring Drive Registration Open", "category": "Placement", "content": "Eligible students with CGPA >= 7.5 and 0 active backlogs can register for the upcoming IBM Cloud Engineer & Full Stack developer campus drive.", "priority": "Important", "date_posted": "September 06, 2026", "author": "Placement Cell"},
        {"id": 3, "title": "Gandhi Jayanti & Mid-Term Recess Notice", "category": "Holidays", "content": "The university campus and lecture halls will remain closed on October 2nd. Lab practical schedules have been adjusted accordingly.", "priority": "Normal", "date_posted": "September 04, 2026", "author": "Registrar Office"},
        {"id": 4, "title": "Docker & Cloud Computing Lab Schedule Revised", "category": "Academic", "content": "Additional lab hours have been allocated every Wednesday afternoon from 2:00 PM to 5:00 PM for hands-on containerization practice.", "priority": "Normal", "date_posted": "September 02, 2026", "author": "Dept. of Computer Science"},
    ],
    "container_status": {
        "frontend": {"name": "frontend-service", "tier": "Frontend", "status": "Running", "state": "healthy",
                     "port": "3000 -> 80/tcp", "uptime": "1d 10h 32m", "container_id": "c7f9104b2a88",
                     "image": "college-portal-frontend:latest", "cpu_percent": 0.8, "memory_mb": 28.4,
                     "health": "200 OK (HTTP GET /)"},
        "backend": {"name": "backend-api", "tier": "Backend API", "status": "Running", "state": "healthy",
                    "port": "5000/tcp", "uptime": "1d 10h 32m", "container_id": "b148ad319c50",
                    "image": "college-portal-backend:latest", "cpu_percent": 1.4, "memory_mb": 68.2,
                    "health": "200 OK (HTTP GET /api/health)"},
        "database": {"name": "database-postgres", "tier": "Database", "status": "Connected", "state": "healthy",
                     "port": "5432/tcp", "uptime": "1d 10h 32m", "container_id": "d993ef50811e",
                     "image": "postgres:16-alpine", "cpu_percent": 2.1, "memory_mb": 114.6,
                     "health": "Connected (pg_isready: healthy)"},
    },
}


# ---------------------------------------------------------------------------
# PostgreSQL connection attempt (optional — falls back to in-memory store)
# ---------------------------------------------------------------------------
def init_db():
    global _is_pg_connected, _db_mode
    if not HAS_PSYCOPG2:
        _is_pg_connected = False
        _db_mode = "Resilient In-Memory Adapter (Zero-Config Mode)"
        STORE["container_status"]["database"]["status"] = "Connected"
        STORE["container_status"]["database"]["health"] = "Connected (In-Memory PostgreSQL Mirror)"
        return
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute("SELECT version()")
        version = cur.fetchone()[0]
        cur.close()
        conn.close()
        _is_pg_connected = True
        _db_mode = "PostgreSQL 16 (Live Engine)"
        print(f"[DB] Connected successfully to PostgreSQL: {version.split(',')[0]}")
        STORE["container_status"]["database"]["status"] = "Connected"
        STORE["container_status"]["database"]["health"] = "Connected (PostgreSQL 16 Live)"
    except Exception as err:
        _is_pg_connected = False
        _db_mode = "Resilient In-Memory Adapter (Zero-Config Mode)"
        print(f"[DB] PostgreSQL not running ({err}). Using in-memory storage adapter with complete relational dataset.")
        STORE["container_status"]["database"]["status"] = "Connected"
        STORE["container_status"]["database"]["health"] = "Connected (In-Memory PostgreSQL Mirror)"


def is_pg_connected():
    return _is_pg_connected


def get_db_mode():
    return _db_mode


def get_store():
    return STORE


# ---------------------------------------------------------------------------
# Container telemetry (mirrors getContainerStatus / simulateAction)
# ---------------------------------------------------------------------------
def get_container_status():
    try:
        import resource
        mem_mb = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)
    except Exception:
        mem_mb = STORE["container_status"]["backend"]["memory_mb"]

    STORE["container_status"]["backend"]["memory_mb"] = mem_mb
    STORE["container_status"]["backend"]["uptime"] = f"{int(time.time() - _start_time)}s"

    return {
        "frontend": STORE["container_status"]["frontend"],
        "backend": STORE["container_status"]["backend"],
        "database": STORE["container_status"]["database"],
        "dbEngine": _db_mode,
        "network": "college-net (bridge)",
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


def simulate_action(tier, action):
    cs = STORE["container_status"]
    if tier not in cs:
        return False
    if action == "restart":
        cs[tier]["status"] = "Restarting"
        cs[tier]["state"] = "starting"

        def _recover():
            cs[tier]["status"] = "Connected" if tier == "database" else "Running"
            cs[tier]["state"] = "healthy"

        import threading
        threading.Timer(2.0, _recover).start()
        return True
    if action == "health_probe":
        cs[tier]["health"] = f"Probe PASSED at {datetime.now().strftime('%H:%M:%S')}"
        return True
    return False


init_db()
