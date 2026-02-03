-- Students table: stores user accounts (both students and admins)
CREATE TABLE students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT DEFAULT 'student' CHECK(role IN ('student','admin'))
);

-- Problems table: stores programming problems
CREATE TABLE problems (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    language TEXT NOT NULL CHECK(language IN ('python','c','cpp'))
);

-- Test cases table: stores input/output pairs for each problem
CREATE TABLE test_cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    problem_id INTEGER NOT NULL,
    input TEXT NOT NULL,
    expected_output TEXT NOT NULL,
    FOREIGN KEY(problem_id) REFERENCES problems(id) ON DELETE CASCADE
);

-- Submissions table: stores student submissions and grading results
CREATE TABLE submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    problem_id INTEGER NOT NULL,
    code TEXT NOT NULL,
    language TEXT NOT NULL CHECK(language IN ('python','c','cpp')),
    score INTEGER DEFAULT 0,
    penalty INTEGER DEFAULT 0,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE,
    FOREIGN KEY(problem_id) REFERENCES problems(id) ON DELETE CASCADE
);

-- Indexes for faster lookups
CREATE INDEX idx_submissions_student ON submissions(student_id);
CREATE INDEX idx_submissions_problem ON submissions(problem_id);
CREATE INDEX idx_testcases_problem ON test_cases(problem_id);
