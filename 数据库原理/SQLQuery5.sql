USE SCHOOL;
GO

-- 所有专业及其所属系名称
SELECT M.MajorID, M.MajorName, D.DepartmentName
FROM MAJOR M
INNER JOIN DEPARTMENT D ON M.DepartmentID = D.DepartmentID;
GO

-- 每个系的专业数量
SELECT D.DepartmentID, D.DepartmentName, COUNT(M.MajorID) AS MajorCount
FROM DEPARTMENT D
LEFT JOIN MAJOR M ON D.DepartmentID = M.DepartmentID
GROUP BY D.DepartmentID, D.DepartmentName;
GO

-- 专业数量最多的系
SELECT D.DepartmentID, D.DepartmentName
FROM DEPARTMENT D
LEFT JOIN MAJOR M ON D.DepartmentID = M.DepartmentID
GROUP BY D.DepartmentID, D.DepartmentName
HAVING COUNT(M.MajorID) >= ALL (
    SELECT COUNT(MajorID)
    FROM MAJOR
    GROUP BY DepartmentID
);

-- 每年招生的班级数量
SELECT EntranceYear, COUNT(ClassID) AS ClassCount
FROM CLASS
GROUP BY EntranceYear;
GO

-- 学生人数最多的班级
SELECT C.ClassID
FROM Class C
LEFT JOIN STUDENT S ON C.ClassID = S.ClassID
GROUP BY C.ClassID
HAVING COUNT(S.StudentID)  >= ALL (
    SELECT COUNT(StudentID)
    FROM STUDENT
    GROUP BY ClassID
);
GO

-- 学生人数最多的专业
SELECT M.MajorID, M.MajorName
FROM MAJOR M
LEFT JOIN CLASS C ON M.MajorID = C.MajorID
LEFT JOIN STUDENT S ON C.ClassID = S.ClassID
GROUP BY M.MajorID, M.MajorName
HAVING COUNT(S.StudentID) >= ALL (
    SELECT COUNT(StudentID)
    FROM STUDENT S2
    INNER JOIN CLASS C2 ON S2.ClassID = C2.ClassID
    GROUP BY C2.MajorID
);
GO

-- 学生人数最多的系
SELECT D.DepartmentID, D.DepartmentName
FROM DEPARTMENT D
LEFT JOIN MAJOR M ON D.DepartmentID = M.DepartmentID
LEFT JOIN CLASS C ON M.MajorID = C.MajorID
LEFT JOIN STUDENT S ON C.ClassID = S.ClassID
GROUP BY D.DepartmentID, D.DepartmentName
HAVING COUNT(S.StudentID) >= ALL (
    SELECT COUNT(StudentID)
    FROM STUDENT S2
    INNER JOIN CLASS C2 ON S2.ClassID = C2.ClassID
    INNER JOIN MAJOR M2 ON C2.MajorID = M2.MajorID
    GROUP BY M2.DepartmentID
);
GO
-- 学生人数超过 '0212000' 的班级
SELECT C.ClassID
FROM CLASS C
LEFT JOIN STUDENT S ON C.ClassID = S.ClassID
GROUP BY C.ClassID
HAVING COUNT(S.StudentID) > (
    SELECT COUNT(StudentID)
    FROM STUDENT
    WHERE ClassID = '0212000'
);
GO

-- 尚未招生的专业
SELECT M.MajorID, M.MajorName
FROM MAJOR M
LEFT JOIN CLASS C ON M.MajorID = C.MajorID
WHERE C.MajorID IS NULL;
GO

-- 2000年入学或1979年出生的学生
SELECT S.StudentID, S.StudentName, S.Sex, S.Birthday, S.ClassID
FROM STUDENT S
INNER JOIN CLASS C ON S.ClassID = C.ClassID
WHERE C.EntranceYear = 2000
   OR YEAR(S.Birthday) = 1979;