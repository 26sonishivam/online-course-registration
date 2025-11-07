-- ================================================================================
-- PART 1: DDL (Data Definition Language) - Schema Creation
-- ================================================================================

-- Drop and create the database to ensure a clean slate
DROP DATABASE IF EXISTS online_registration_db_3;
CREATE DATABASE online_registration_db_3 CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
USE online_registration_db_3;

-- Department Table
CREATE TABLE Department (
    Department_ID INT PRIMARY KEY,
    Dept_Name VARCHAR(100) NOT NULL UNIQUE,
    Head_ID INT
);

-- Instructor Table
CREATE TABLE Instructor (
    Instructor_ID INT PRIMARY KEY,
    Name VARCHAR(150) NOT NULL,
    Email VARCHAR(150),
    Specialization VARCHAR(150),
    Department_ID INT,
    FOREIGN KEY (Department_ID) REFERENCES Department(Department_ID)
);

-- Add the foreign key constraint for Department Head after Instructor table is created
ALTER TABLE Department
ADD CONSTRAINT fk_dept_head FOREIGN KEY (Head_ID) REFERENCES Instructor(Instructor_ID);

-- Student Table
CREATE TABLE Student (
    Student_ID INT PRIMARY KEY,
    Name VARCHAR(150) NOT NULL,
    Email VARCHAR(150),
    Year VARCHAR(10),
    Department_ID INT,
    FOREIGN KEY (Department_ID) REFERENCES Department(Department_ID)
);

-- Classroom Table
CREATE TABLE Classroom (
    Room_ID INT PRIMARY KEY,
    Location VARCHAR(150),
    Capacity INT NOT NULL
);

-- Course Table (Using VARCHAR for Course_ID and Prerequisite_ID)
CREATE TABLE Course (
    Course_ID VARCHAR(20) PRIMARY KEY,
    Course_Name VARCHAR(255) NOT NULL,
    Credits INT NOT NULL,
    Department_ID INT,
    Semester_Offered VARCHAR(50),
    Prerequisite_ID VARCHAR(20) DEFAULT NULL,
    FOREIGN KEY (Department_ID) REFERENCES Department(Department_ID),
    CONSTRAINT fk_course_prereq FOREIGN KEY (Prerequisite_ID) REFERENCES Course(Course_ID)
);

-- Course Schedule Table
CREATE TABLE Course_Schedule (
    Schedule_ID INT PRIMARY KEY,
    Course_ID VARCHAR(20) NOT NULL,
    Instructor_ID INT NOT NULL,
    Room_ID INT NOT NULL,
    Day VARCHAR(50),
    Time VARCHAR(50),
    FOREIGN KEY (Course_ID) REFERENCES Course(Course_ID),
    FOREIGN KEY (Instructor_ID) REFERENCES Instructor(Instructor_ID),
    FOREIGN KEY (Room_ID) REFERENCES Classroom(Room_ID)
);

-- Registration Table (FIXED: Reg_ID is now AUTO_INCREMENT)
CREATE TABLE Registration (
    Reg_ID INT AUTO_INCREMENT PRIMARY KEY, -- This line is corrected
    Student_ID INT NOT NULL,
    Schedule_ID INT NOT NULL,
    Semester VARCHAR(20) NOT NULL,
    Grade CHAR(2) DEFAULT NULL,
    FOREIGN KEY (Student_ID) REFERENCES Student(Student_ID),
    FOREIGN KEY (Schedule_ID) REFERENCES Course_Schedule(Schedule_ID)
);

-- Payment Table
CREATE TABLE Payment (
    Payment_ID INT PRIMARY KEY,
    Reg_ID INT NOT NULL,
    Amount DECIMAL(10,2),
    Payment_Date DATE,
    Method VARCHAR(50),
    FOREIGN KEY (Reg_ID) REFERENCES Registration(Reg_ID)
);

-- Grade Change Audit Table
CREATE TABLE GradeChangeAudit (
    Log_ID INT AUTO_INCREMENT PRIMARY KEY,
    Reg_ID INT,
    Student_ID INT,
    Old_Grade CHAR(2),
    New_Grade CHAR(2),
    Change_Timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ================================================================================
-- PART 2: Database Objects (Functions, Procedures, Triggers)
-- ================================================================================

DELIMITER $$

-- Function: GetAvailableSeats
DROP FUNCTION IF EXISTS GetAvailableSeats$$
CREATE FUNCTION GetAvailableSeats(sid INT) RETURNS INT
DETERMINISTIC
BEGIN
    DECLARE cap INT DEFAULT 0;
    DECLARE enrolled INT DEFAULT 0;
    SELECT Capacity INTO cap FROM Classroom WHERE Room_ID = (SELECT Room_ID FROM Course_Schedule WHERE Schedule_ID = sid);
    SELECT COUNT(*) INTO enrolled FROM Registration WHERE Schedule_ID = sid;
    RETURN IFNULL(cap - enrolled, 0);
END$$

-- Function: HasCompletedPrerequisite (Updated to accept VARCHAR Course ID)
DROP FUNCTION IF EXISTS HasCompletedPrerequisite$$
CREATE FUNCTION HasCompletedPrerequisite(sid INT, cid VARCHAR(20)) RETURNS TINYINT
DETERMINISTIC
BEGIN
    DECLARE pre VARCHAR(20);
    DECLARE passed INT DEFAULT 0;
    SELECT Prerequisite_ID INTO pre FROM Course WHERE Course_ID = cid;
    IF pre IS NULL THEN
        RETURN 1; -- No prerequisite
    END IF;
    -- Check if the student has a registration for the prerequisite with a passing grade
    SELECT COUNT(*) INTO passed
    FROM Registration r
    JOIN Course_Schedule cs ON r.Schedule_ID = cs.Schedule_ID
    WHERE r.Student_ID = sid
      AND cs.Course_ID = pre
      AND r.Grade IS NOT NULL
      AND r.Grade <> 'F';
    RETURN IF(passed > 0, 1, 0);
END$$

DELIMITER ;

DELIMITER $$

-- Stored Procedure: UpdateStudentGrade
DROP PROCEDURE IF EXISTS UpdateStudentGrade$$
CREATE PROCEDURE UpdateStudentGrade(IN regId INT, IN newGrade CHAR(2))
BEGIN
    UPDATE Registration
    SET Grade = newGrade
    WHERE Reg_ID = regId;
END$$

DELIMITER ;

DELIMITER $$

-- Trigger: trg_AfterGradeUpdate
DROP TRIGGER IF EXISTS trg_AfterGradeUpdate$$
CREATE TRIGGER trg_AfterGradeUpdate
AFTER UPDATE ON Registration
FOR EACH ROW
BEGIN
    IF (OLD.Grade IS NULL AND NEW.Grade IS NOT NULL)
       OR (OLD.Grade IS NOT NULL AND NEW.Grade IS NULL)
       OR (OLD.Grade <> NEW.Grade) THEN
        INSERT INTO GradeChangeAudit (Reg_ID, Student_ID, Old_Grade, New_Grade)
        VALUES (OLD.Reg_ID, OLD.Student_ID, OLD.Grade, NEW.Grade);
    END IF;
END$$

DELIMITER ;

-- ================================================================================
-- PART 3: DML (Data Manipulation Language) - Sample Data Insertion & Updates
-- ================================================================================

-- Inserting Departments
INSERT INTO Department (Department_ID, Dept_Name) VALUES (101, 'Computer Science (CSE)'), (102, 'Electrical & Electronics (EEE)');

-- Inserting Classrooms
INSERT INTO Classroom (Room_ID, Capacity, Location) VALUES (501, 70, 'Golden Jubilee Block'), (502, 60, 'Panini Block'), (310, 50, 'BE-block');

-- Inserting Instructors
INSERT INTO Instructor (Instructor_ID, Name, Email, Specialization, Department_ID) VALUES
(201, 'Dr. Priya Sharma', 'priya_the_prof@uni.edu', 'Database Systems', 101),
(202, 'Prof. Rohan Menon', 'rohan_codes_alot@uni.edu', 'Adv. Machine Learning', 101),
(203, 'Dr. Ananya Reddy', 'dr_ananya_rules@uni.edu', 'Embedded Systems', 102),
(204, 'Dr. Sameer Khan', 'khan_secures_it@uni.edu', 'Cyber Security', 101),
(205, 'Prof. Divya Nair', 'divya_designs_reality@uni.edu', 'Augmented Reality', 102),
(206, 'Prof. Arjun Desai', 'arjun_builds_models@uni.edu', 'Machine Learning', 101);

-- Updating Department Heads
UPDATE Department SET Head_ID = 201 WHERE Department_ID = 101;
UPDATE Department SET Head_ID = 203 WHERE Department_ID = 102;

-- Inserting Students
INSERT INTO Student (Student_ID, Name, Email, Year, Department_ID) VALUES
(1001, 'Vikram Singh', 'vicky_singh@uni.edu', 3, 101), (1002, 'Meera Iyer', 'meera_iyer99@uni.edu', 3, 101),
(1003, 'Arjun Gupta', 'arjun_g_rocks@uni.edu', 4, 101), (1004, 'Lakshmi Patel', 'lucky_lakshmi@uni.edu', 4, 101),
(1005, 'Sneha Rao', 'sneha_rao123@uni.edu', 3, 101), (1006, 'Aditya Kumar', 'adi_kumar@uni.edu', 4, 101),
(1007, 'Nithya Krishnan', 'nithya_k@uni.edu', 3, 102), (1008, 'Sameer Joshi', 'sam_j@uni.edu', 3, 102),
(1009, 'Fatima Begum', 'fatima_b@uni.edu', 4, 102), (1010, 'Karthik Subramanian', 'karthik_sub@uni.edu', 3, 102);

-- Add Phone column to Student table as per the ER diagram
ALTER TABLE Student ADD COLUMN Phone VARCHAR(20);

-- Updating Students with Phone Numbers
UPDATE Student SET Phone = '555-0101' WHERE Student_ID = 1001;
UPDATE Student SET Phone = '555-0102' WHERE Student_ID = 1002;
UPDATE Student SET Phone = '555-0103' WHERE Student_ID = 1003;
UPDATE Student SET Phone = '555-0104' WHERE Student_ID = 1004;
UPDATE Student SET Phone = '555-0105' WHERE Student_ID = 1005;
UPDATE Student SET Phone = '555-0106' WHERE Student_ID = 1006;
UPDATE Student SET Phone = '555-0107' WHERE Student_ID = 1007;
UPDATE Student SET Phone = '555-0108' WHERE Student_ID = 1008;
UPDATE Student SET Phone = '555-0109' WHERE Student_ID = 1009;
UPDATE Student SET Phone = '555-0110' WHERE Student_ID = 1010;

-- Inserting Courses
INSERT INTO Course (Course_ID, Course_Name, Credits, Semester_Offered, Department_ID, Prerequisite_ID) VALUES
('CS350', 'Machine Learning', 4, 5, 101, NULL), ('CS351', 'Database Management (DBMS)', 4, 5, 101, NULL),
('CS401', 'Adv Foundation for Machine Learning (AFML)', 4, 6, 101, 'CS350'), ('CS402', 'Cyber Security', 3, 6, 101, NULL),
('EE501', 'AR / VR', 3, 6, 102, NULL), ('EE502', 'Internet of Things (IOT)', 4, 5, 102, NULL);

-- Creating Course Schedules
INSERT INTO Course_Schedule (Schedule_ID, Course_ID, Instructor_ID, Room_ID, Day, Time) VALUES
(901, 'CS351', 201, 501, 'Monday, Wednesday', '10:00 AM - 12:00 PM'), (902, 'CS402', 204, 501, 'Friday', '9:00 AM - 12:00 PM'),
(903, 'CS350', 206, 502, 'Tuesday, Thursday', '10:00 AM - 12:00 PM'),(904, 'CS401', 202, 502, 'Tuesday, Thursday', '2:00 PM - 4:00 PM'),
(905, 'EE502', 203, 310, 'Tuesday, Thursday', '10:00 AM - 12:00 PM'),(906, 'EE501', 205, 310, 'Monday, Wednesday', '2:00 PM - 3:30 PM');

-- Inserting Registrations
-- NOTE: We can still insert with explicit IDs into an AUTO_INCREMENT column.
-- The auto-increment counter will simply adjust to the highest ID inserted.
INSERT INTO Registration (Reg_ID, Student_ID, Schedule_ID, Semester, Grade) VALUES
(1, 1003, 903, 'Semester 5', 'A'), (2, 1004, 903, 'Semester 5', 'B'), (3, 1006, 903, 'Semester 5', 'A'),
(4, 1001, 901, 'Semester 5', 'A'), (5, 1001, 903, 'Semester 5', NULL), (6, 1002, 901, 'Semester 5', 'B'),
(7, 1002, 903, 'Semester 5', NULL), (8, 1005, 901, 'Semester 5', 'C'), (9, 1005, 905, 'Semester 5', NULL),
(10, 1007, 903, 'Semester 5', NULL),(11, 1007, 905, 'Semester 5', 'A'), (12, 1008, 901, 'Semester 5', 'C'),
(13, 1008, 905, 'Semester 5', 'B'), (14, 1010, 903, 'Semester 5', NULL),(15, 1010, 905, 'Semester 5', 'A'),
(16, 1003, 902, 'Semester 6', NULL),(17, 1003, 904, 'Semester 6', NULL), (18, 1004, 902, 'Semester 6', NULL),
(19, 1004, 906, 'Semester 6', NULL), (20, 1006, 904, 'Semester 6', 'A'),(21, 1006, 906, 'Semester 6', NULL),
(22, 1009, 902, 'Semester 6', NULL),(23, 1009, 906, 'Semester 6', NULL);

-- Inserting Sample Payments
INSERT INTO Payment (Payment_ID, Reg_ID, Amount, Payment_Date, Method) VALUES
(8001, 4, 250.00, '2025-08-15', 'Credit Card'), 
(8002, 6, 250.00, '2025-08-16', 'Net Banking'),
(8003, 1, 300.00, '2025-01-20', 'Credit Card');