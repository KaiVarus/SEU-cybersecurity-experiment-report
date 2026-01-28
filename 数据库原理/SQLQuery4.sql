-- Simple Queries
USE SCHOOL;

-- Students with last name '张', youngest to oldest
SELECT StudentID, StudentName, Sex, Birthday, ClassID
FROM STUDENT
WHERE StudentName LIKE N'张%'
ORDER BY Birthday DESC;
GO

-- Students in '计算机科学与技术' department
SELECT S.*
FROM STUDENT S
INNER JOIN CLASS C ON S.ClassID = C.ClassID
INNER JOIN MAJOR M ON C.MajorID = M.MajorID
INNER JOIN DEPARTMENT D ON M.DepartmentID = D.DepartmentID
WHERE D.DepartmentName = N'计算机科学与技术';
GO

-- Students enrolled in 2001
SELECT S.*
FROM STUDENT S
INNER JOIN CLASS C ON S.ClassID = C.ClassID
WHERE C.EntranceYear = 2001;
GO

-- Department for '张三'
SELECT D.DepartmentID, D.DepartmentName
FROM STUDENT S
INNER JOIN CLASS C ON S.ClassID = C.ClassID
INNER JOIN MAJOR M ON C.MajorID = M.MajorID
INNER JOIN DEPARTMENT D ON M.DepartmentID = D.DepartmentID
WHERE S.StudentName = N'张三';
GO

-- Classmates of '张三'
SELECT StudentID, StudentName
FROM STUDENT
WHERE ClassID = (SELECT ClassID FROM STUDENT WHERE StudentName = N'张三')
ORDER BY StudentID;