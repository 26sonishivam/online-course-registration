# app.py
from flask import Flask, render_template, request, jsonify, redirect, url_for
import mysql.connector
from mysql.connector import Error
from datetime import datetime
import json

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'

# Database configuration - update password/user/host as needed
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'Shivam@2644',
    'database': 'online_registration_db_3'
}

def get_db_connection():
    """Create and return a database connection"""
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        return connection
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        return None

def execute_query(query, params=None, fetch=True):
    """Execute a query and return results"""
    connection = get_db_connection()
    if not connection:
        return None
    
    try:
        cursor = connection.cursor(dictionary=True)
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        
        if fetch:
            result = cursor.fetchall()
        else:
            connection.commit()
            result = cursor.lastrowid
        
        cursor.close()
        connection.close()
        return result
    except Error as e:
        print(f"Error executing query: {e}")
        if connection:
            connection.close()
        return None

# -------------------------
# ROUTES
# -------------------------
@app.route('/')
def index():
    """Main page (assumes frontend files)"""
    return render_template('index.html')

# ----- listing endpoints for frontend dynamic switching -----
@app.route('/api/students')
def list_students():
    q = "SELECT Student_ID, Name FROM Student ORDER BY Name"
    res = execute_query(q)
    return jsonify(res if res else [])

@app.route('/api/instructors')
def list_instructors():
    q = "SELECT Instructor_ID, Name FROM Instructor ORDER BY Name"
    res = execute_query(q)
    return jsonify(res if res else [])

# ----- Student registrations -----
@app.route('/api/student/<int:student_id>/registrations')
def get_student_registrations(student_id):
    query = """
        SELECT 
            r.Reg_ID,
            r.Semester,
            r.Grade,
            c.Course_ID,
            c.Course_Name,
            c.Credits,
            i.Instructor_ID,
            i.Name as Instructor_Name,
            cs.Schedule_ID,
            cs.Day,
            cs.Time,
            cl.Location
        FROM Registration r
        JOIN Course_Schedule cs ON r.Schedule_ID = cs.Schedule_ID
        JOIN Course c ON cs.Course_ID = c.Course_ID
        JOIN Instructor i ON cs.Instructor_ID = i.Instructor_ID
        JOIN Classroom cl ON cs.Room_ID = cl.Room_ID
        WHERE r.Student_ID = %s
        ORDER BY r.Semester, c.Course_Name
    """
    result = execute_query(query, (student_id,))
    return jsonify(result if result else [])

@app.route('/api/available-courses/<int:student_id>')
def get_available_courses(student_id):
    """Get available courses for registration"""
    # Get student's department
    student_query = "SELECT Department_ID FROM Student WHERE Student_ID = %s"
    student = execute_query(student_query, (student_id,))
    
    if not student:
        return jsonify([])

    dept_id = student[0]['Department_ID']

    query = """
        SELECT 
            cs.Schedule_ID,
            c.Course_ID,
            c.Course_Name,
            c.Credits,
            c.Semester_Offered,
            c.Prerequisite_ID,
            i.Instructor_ID,
            i.Name as Instructor_Name,
            cl.Room_ID,
            cl.Capacity,
            cl.Location,
            cs.Day,
            cs.Time,
            (SELECT COUNT(*) FROM Registration WHERE Schedule_ID = cs.Schedule_ID) as Enrolled
        FROM Course_Schedule cs
        JOIN Course c ON cs.Course_ID = c.Course_ID
        JOIN Instructor i ON cs.Instructor_ID = i.Instructor_ID
        JOIN Classroom cl ON cs.Room_ID = cl.Room_ID
        WHERE c.Department_ID = %s
        ORDER BY c.Course_Name
    """
    courses = execute_query(query, (dept_id,))
    if not courses:
        return jsonify([])

    for course in courses:
        course['Available_Seats'] = course['Capacity'] - (course['Enrolled'] or 0)

        # Check if already registered
        reg_check = execute_query(
            "SELECT 1 FROM Registration WHERE Student_ID = %s AND Schedule_ID = %s",
            (student_id, course['Schedule_ID'])
        )
        course['Is_Registered'] = len(reg_check) > 0 if reg_check else False

    return jsonify(courses)


@app.route('/api/register-course', methods=['POST'])
def register_course():
    """Register a student for a course"""
    data = request.json
    student_id = data.get('student_id')
    schedule_id = data.get('schedule_id')
    semester = data.get('semester', 'Semester 6')

    if not student_id or not schedule_id:
        return jsonify({'success': False, 'message': 'student_id and schedule_id required'})

    connection = get_db_connection()
    if not connection:
        return jsonify({'success': False, 'message': 'Database connection failed'})

    try:
        cursor = connection.cursor(dictionary=True) # Use dictionary cursor for easier access

        # Check duplicate registration
        cursor.execute(
            "SELECT Reg_ID FROM Registration WHERE Student_ID = %s AND Schedule_ID = %s",
            (student_id, schedule_id)
        )
        if cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({'success': False, 'message': 'Already registered for this schedule'})

        # Check available seats using function
        cursor.execute("SELECT GetAvailableSeats(%s) as seats", (schedule_id,))
        result = cursor.fetchone()
        available_seats = result['seats'] if result else 0

        if available_seats <= 0:
            cursor.close()
            connection.close()
            return jsonify({'success': False, 'message': 'Class is full (Function blocked)'})

        # Get course_id from schedule
        cursor.execute("SELECT Course_ID FROM Course_Schedule WHERE Schedule_ID = %s", (schedule_id,))
        row = cursor.fetchone()
        course_id = row['Course_ID'] if row else None

        # Check prerequisite (if any)
        if course_id:
            cursor.execute("SELECT HasCompletedPrerequisite(%s, %s) as completed", (student_id, course_id))
            prereq_result = cursor.fetchone()
            has_prereq = prereq_result['completed'] if prereq_result else 0
            if not has_prereq:
                cursor.close()
                connection.close()
                return jsonify({'success': False, 'message': 'Prerequisite not completed (Function blocked)'})

        # Insert registration - Reg_ID is AUTO_INCREMENT in SQL schema
        insert_cursor = connection.cursor()
        insert_cursor.execute(
            "INSERT INTO Registration (Student_ID, Schedule_ID, Semester, Grade) VALUES (%s, %s, %s, NULL)",
            (student_id, schedule_id, semester)
        )
        connection.commit()
        reg_id = insert_cursor.lastrowid
        
        insert_cursor.close()
        cursor.close()
        connection.close()

        return jsonify({'success': True, 'message': f'Successfully registered! Reg ID: {reg_id}', 'reg_id': reg_id})
    except Error as e:
        if connection:
            connection.close()
        return jsonify({'success': False, 'message': f'Registration failed: {str(e)}'})

@app.route('/api/drop-course', methods=['POST'])
def drop_course():
    data = request.json
    reg_id = data.get('reg_id')
    student_id = data.get('student_id')

    if not reg_id or not student_id:
        return jsonify({'success': False, 'message': 'reg_id and student_id required'})

    connection = get_db_connection()
    if not connection:
        return jsonify({'success': False, 'message': 'Database connection failed'})

    try:
        cursor = connection.cursor()

        # Verify registration belongs to student
        cursor.execute("SELECT 1 FROM Registration WHERE Reg_ID = %s AND Student_ID = %s", (reg_id, student_id))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({'success': False, 'message': 'Registration not found or unauthorized'})

        # Check payment exists
        cursor.execute("SELECT 1 FROM Payment WHERE Reg_ID = %s", (reg_id,))
        if cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({'success': False, 'message': 'Cannot drop course: Payment has been made.'})

        cursor.execute("DELETE FROM Registration WHERE Reg_ID = %s AND Student_ID = %s", (reg_id, student_id))
        connection.commit()

        cursor.close()
        connection.close()
        return jsonify({'success': True, 'message': f'Registration {reg_id} dropped successfully'})

    except Error as e:
        if connection:
            connection.rollback()
            connection.close()
        return jsonify({'success': False, 'message': f'Failed to drop course: {str(e)}'})

@app.route('/api/check-prerequisite', methods=['POST'])
def check_prerequisite():
    data = request.json
    student_id = data.get('student_id')
    course_id = data.get('course_id')

    if not student_id or not course_id:
        return jsonify({'success': False, 'message': 'student_id and course_id required'})

    connection = get_db_connection()
    if not connection:
        return jsonify({'success': False, 'message': 'Database connection failed'})

    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT Course_Name, Prerequisite_ID FROM Course WHERE Course_ID = %s", (course_id,))
        course = cursor.fetchone()
        if not course:
            cursor.close()
            connection.close()
            return jsonify({'success': False, 'message': 'Course not found'})

        cursor.execute("SELECT HasCompletedPrerequisite(%s, %s) as completed", (student_id, course_id))
        result = cursor.fetchone()
        completed = result['completed'] if result else False

        cursor.close()
        connection.close()
        return jsonify({'success': True, 'course_name': course['Course_Name'], 'prerequisite_id': course['Prerequisite_ID'], 'has_completed': bool(completed)})
    except Error as e:
        if connection:
            connection.close()
        return jsonify({'success': False, 'message': str(e)})

# --- ADMIN ROUTES ---

# THIS IS THE NEW, FILTERED ENDPOINT
@app.route('/api/instructor/<int:instructor_id>/registrations')
def get_instructor_registrations(instructor_id):
    """Get all registrations for a specific instructor's courses."""
    query = """
        SELECT 
            r.Reg_ID,
            r.Student_ID,
            s.Name as Student_Name,
            c.Course_ID,
            c.Course_Name,
            r.Semester,
            r.Grade
        FROM Registration r
        JOIN Student s ON r.Student_ID = s.Student_ID
        JOIN Course_Schedule cs ON r.Schedule_ID = cs.Schedule_ID
        JOIN Course c ON cs.Course_ID = c.Course_ID
        WHERE cs.Instructor_ID = %s
        ORDER BY r.Reg_ID
    """
    result = execute_query(query, (instructor_id,))
    return jsonify(result if result else [])

# This old endpoint is no longer used for grade management but is kept for reference
@app.route('/api/all-registrations')
def get_all_registrations():
    query = """
        SELECT 
            r.Reg_ID,
            r.Student_ID,
            s.Name as Student_Name,
            c.Course_ID,
            c.Course_Name,
            r.Semester,
            r.Grade
        FROM Registration r
        JOIN Student s ON r.Student_ID = s.Student_ID
        JOIN Course_Schedule cs ON r.Schedule_ID = cs.Schedule_ID
        JOIN Course c ON cs.Course_ID = c.Course_ID
        ORDER BY r.Reg_ID
    """
    result = execute_query(query)
    return jsonify(result if result else [])

@app.route('/api/update-grade', methods=['POST'])
def update_grade():
    """Update student grade using stored procedure (procedure only updates Registration)"""
    data = request.json
    reg_id = data.get('reg_id')
    new_grade = data.get('new_grade')

    if new_grade == 'NULL':
        new_grade = None

    connection = get_db_connection()
    if not connection:
        return jsonify({'success': False, 'message': 'Database connection failed'})

    try:
        cursor = connection.cursor()
        # Call stored procedure UpdateStudentGrade(regId, newGrade)
        cursor.callproc('UpdateStudentGrade', [reg_id, new_grade])
        connection.commit()
        cursor.close()
        connection.close()
        # Trigger will insert into GradeChangeAudit automatically
        return jsonify({'success': True, 'message': f'Grade updated successfully for Reg ID {reg_id}'})
    except Error as e:
        if connection:
            connection.close()
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/audit-log')
def get_audit_log():
    query = """
        SELECT 
            Log_ID,
            Reg_ID,
            Student_ID,
            Old_Grade,
            New_Grade,
            Change_Timestamp
        FROM GradeChangeAudit
        ORDER BY Log_ID DESC
    """
    result = execute_query(query)
    # Convert timestamp to a more readable format
    if result:
        for row in result:
            if row['Change_Timestamp']:
                row['Change_Timestamp'] = row['Change_Timestamp'].strftime('%Y-%m-%d %H:%M:%S')
    return jsonify(result if result else [])

# Example queries endpoints (left as in original)
@app.route('/api/query/join')
def query_join():
    query = """
        SELECT 
            s.Name as Student_Name,
            c.Course_Name,
            p.Amount,
            p.Payment_Date,
            p.Method
        FROM Student s
        JOIN Registration r ON s.Student_ID = r.Student_ID
        JOIN Payment p ON r.Reg_ID = p.Reg_ID
        JOIN Course_Schedule cs ON r.Schedule_ID = cs.Schedule_ID
        JOIN Course c ON cs.Course_ID = c.Course_ID
        ORDER BY p.Payment_Date DESC
    """
    result = execute_query(query)
    return jsonify(result if result else [])

@app.route('/api/query/nested')
def query_nested():
    query = """
        SELECT 
            s.Student_ID,
            s.Name as Student_Name
        FROM Student s
        WHERE s.Student_ID IN (
            SELECT DISTINCT r.Student_ID
            FROM Registration r
            JOIN Course_Schedule cs ON r.Schedule_ID = cs.Schedule_ID
            WHERE cs.Instructor_ID = 201 -- Hardcoded for Dr. Priya Sharma as per original
        )
        ORDER BY s.Name
    """
    result = execute_query(query)
    return jsonify(result if result else [])

@app.route('/api/query/aggregate')
def query_aggregate():
    query = """
        SELECT 
            d.Dept_Name as Department_Name,
            COUNT(c.Course_ID) as Number_of_Courses
        FROM Department d
        JOIN Course c ON d.Department_ID = c.Department_ID
        GROUP BY d.Dept_Name
        ORDER BY Number_of_Courses DESC
    """
    result = execute_query(query)
    return jsonify(result if result else [])

@app.route('/api/student/<int:student_id>')
def get_student_info(student_id):
    query = """
        SELECT 
            s.Student_ID,
            s.Name,
            s.Email,
            s.Year,
            s.Phone,
            d.Dept_Name as Department
        FROM Student s
        JOIN Department d ON s.Department_ID = d.Department_ID
        WHERE s.Student_ID = %s
    """
    result = execute_query(query, (student_id,))
    return jsonify(result[0] if result else {})

@app.route('/api/instructor/<int:instructor_id>')
def get_instructor_info(instructor_id):
    query = """
        SELECT 
            i.Instructor_ID,
            i.Name,
            i.Email,
            i.Specialization,
            d.Dept_Name as Department
        FROM Instructor i
        JOIN Department d ON i.Department_ID = d.Department_ID
        WHERE i.Instructor_ID = %s
    """
    result = execute_query(query, (instructor_id,))
    return jsonify(result[0] if result else {})

if __name__ == '__main__':
    app.run(debug=True, port=5000)