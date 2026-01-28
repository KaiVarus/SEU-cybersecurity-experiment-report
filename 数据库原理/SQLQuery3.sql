-- Insert Data
USE SCHOOL;

-- DEPARTMENT
IF NOT EXISTS (SELECT 1 FROM DEPARTMENT WHERE DepartmentID IN ('01','02','11'))
BEGIN
    INSERT INTO DEPARTMENT (DepartmentID, DepartmentName, DepartmentDesc) VALUES
    ('01', N'计算机科学与技术', N'略'),
    ('02', N'自动化',         N'略'),
    ('11', N'电子科学与技术', N'略');
    PRINT 'DEPARTMENT 数据插入完成';
END
GO

-- MAJOR
IF NOT EXISTS (SELECT 1 FROM MAJOR WHERE MajorID IN ('011','012','021','111'))
BEGIN
    INSERT INTO MAJOR VALUES
    ('011', N'计算机应用技术', N'略', '01'),
    ('012', N'计算机软件技术', N'略', '01'),
    ('021', N'自动控制',       N'略', '02'),
    ('111', N'电路与系统',     N'略', '11');
    PRINT 'MAJOR 数据插入完成';
END
GO

-- CLASS
IF NOT EXISTS (SELECT 1 FROM CLASS WHERE ClassID LIKE '[0-9][0-9][0-9]200[0-1]')
BEGIN
    INSERT INTO CLASS VALUES
    ('0112000', '011', 2000),
    ('0112001', '011', 2001),
    ('0122000', '012', 2000),
    ('0122001', '012', 2001),
    ('0212000', '021', 2000);
    PRINT 'CLASS 数据插入完成';
END
GO

-- STUDENT
IF NOT EXISTS (SELECT 1 FROM STUDENT WHERE StudentID LIKE '0%')
BEGIN
    INSERT INTO STUDENT VALUES
    ('0112000001', N'张三', N'男', '1980-01-10', '0112000'),
    ('0112000002', N'钱四', N'男', '1980-02-11', '0112000'),
    ('0112000003', N'王玲', N'女', '1980-04-24', '0112000'),
    ('0112000004', N'王菲', N'女', '1980-04-24', '0112000'),
    ('0112001001', N'李飞', N'男', '1981-02-10', '0112001'),
    ('0112001002', N'赵四', N'男', '1983-06-13', '0112001'),
    ('0122000001', N'李可', N'女', '1983-03-03', '0122000'),
    ('0122000002', N'张飞', N'男', '1980-05-05', '0122000'),
    ('0122001001', N'周瑜', N'男', '1980-02-12', '0122001'),
    ('0122001002', N'王亮', N'男', '1980-04-08', '0122001'),
    ('0212000001', N'董庆', N'男', '1980-02-12', '0212000'),
    ('0212000002', N'赵龙', N'男', '1980-01-10', '0212000'),
    ('0212000003', N'李丽', N'女', '1980-05-10', '0212000');
    PRINT 'STUDENT 数据插入完成（共13行）';
END
ELSE PRINT 'STUDENT 数据已存在，跳过插入';