-- Create Database
IF DB_ID('SCHOOL') IS NULL
BEGIN
    PRINT '创建数据库 SCHOOL';
    CREATE DATABASE SCHOOL;
END
ELSE
    PRINT '数据库 SCHOOL 已存在，跳过创建。';