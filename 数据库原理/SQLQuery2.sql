USE SCHOOL;

-- DEPARTMENT
IF OBJECT_ID('dbo.DEPARTMENT', 'U') IS NULL
BEGIN
    CREATE TABLE DEPARTMENT (
        DepartmentID   CHAR(2)      PRIMARY KEY,
        DepartmentName  VARCHAR(30)  NOT NULL UNIQUE,
        DepartmentDesc  VARCHAR(1000)
    );
    PRINT '表 DEPARTMENT 创建成功';
END
ELSE PRINT '表 DEPARTMENT 已存在，跳过创建';
GO

-- MAJOR
IF OBJECT_ID('dbo.MAJOR', 'U') IS NULL
BEGIN
    CREATE TABLE MAJOR (
        MajorID        CHAR(3)      PRIMARY KEY,
        MajorName      VARCHAR(30)  NOT NULL,
        MajorDesc      VARCHAR(1000),
        DepartmentID   CHAR(2),
        FOREIGN KEY (DepartmentID) REFERENCES DEPARTMENT(DepartmentID)
    );
    PRINT '表 MAJOR 创建成功';
END
ELSE PRINT '表 MAJOR 已存在，跳过创建';
GO

-- CLASS
IF OBJECT_ID('dbo.CLASS', 'U') IS NULL
BEGIN
    CREATE TABLE CLASS (
        ClassID       CHAR(7) PRIMARY KEY,
        MajorID       CHAR(3),
        EntranceYear  INT CHECK (EntranceYear BETWEEN 1990 AND 2100),
        FOREIGN KEY (MajorID) REFERENCES MAJOR(MajorID)
    );
    PRINT '表 CLASS 创建成功';
END
ELSE PRINT '表 CLASS 已存在，跳过创建';
GO

-- STUDENT
IF OBJECT_ID('dbo.STUDENT', 'U') IS NULL
BEGIN
    CREATE TABLE STUDENT (
        StudentID    CHAR(10)     PRIMARY KEY,
        StudentName  VARCHAR(20)  NOT NULL,
        Sex          CHAR(2)      NOT NULL CHECK (Sex IN (N'男', N'女')),
        Birthday     DATE         NOT NULL,
        ClassID      CHAR(7),
        FOREIGN KEY (ClassID) REFERENCES CLASS(ClassID)
    );
    PRINT '表 STUDENT 创建成功';
END
ELSE PRINT '表 STUDENT 已存在，跳过创建';
GO

-- 年龄触发器（15~50岁）
IF OBJECT_ID('dbo.trg_CheckStudentAge', 'TR') IS NULL
BEGIN
    EXEC('
    CREATE TRIGGER trg_CheckStudentAge
    ON STUDENT
    AFTER INSERT, UPDATE
    AS
    BEGIN
        DECLARE @Today DATE = CAST(GETDATE() AS DATE);
        IF EXISTS (
            SELECT 1 FROM inserted i
            WHERE 
            DATEDIFF(YEAR, i.Birthday, @Today) 
            - CASE WHEN DATEADD(YEAR, DATEDIFF(YEAR, i.Birthday, @Today), i.Birthday) > @Today THEN 1 ELSE 0 END
            NOT BETWEEN 15 AND 50
        )
        BEGIN
            RAISERROR (N''学生年龄必须在15至50岁之间！'', 16, 1);
            ROLLBACK TRANSACTION;
        END
    END');
    PRINT '年龄检查触发器创建成功';
END
ELSE PRINT '年龄触发器已存在，跳过';