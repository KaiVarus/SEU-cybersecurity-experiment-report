#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/types.h>
#include <string.h>
#include <sys/stat.h>
#include <signal.h>
#include <fcntl.h>
#include <ctype.h> // 添加 isdigit 函数的头文件

#define hist_size 1024 // 定义历史记录最大容量

char* hist[hist_size]; // 历史命令数组
int f = 0; // 标记目录是否更改
int head = 0, filled = 0; // 历史记录的头指针和填充计数

// 解析用户输入函数
void parse(char* word, char** argv)
{
    int count = 0;
    memset(argv, 0, sizeof(char*) * (64)); // 初始化参数数组
    char* lefts = NULL;
    const char* split = " "; // 设置空格为分隔符

    // 使用strtok_r分割输入字符串
    while (1)
    {
        char* p = strtok_r(word, split, &lefts);
        if (p == NULL)
        {
            break;
        }
        argv[count] = p; // 存储分割后的参数
        word = lefts;
        count++;
    }

    // 处理退出命令
    if (strcmp(argv[0], "exit") == 0)
        exit(0);
    // 处理cd命令
    else if (strcmp(argv[0], "cd") == 0)
    {
        int ch = chdir(argv[1]); // 更改工作目录
        f = 1; // 标记目录已更改
    }
}

// 去除字符串中空格的函数
char* trim(char* string)
{
    int i = 0;
    int j = 0;
    char* ptr = malloc(sizeof(char*) * strlen(string));

    // 复制非空格字符到新字符串
    for (i = 0; string[i] != '\0'; i++)
        if (string[i] != ' ')
        {
            ptr[j] = string[i];
            j++;
        }

    ptr[j] = '\0'; // 添加字符串结束符
    string = ptr;
    return string;
}

void execute(char** argv)
{
    pid_t pid;
    int status;
    //fork child process
    if ((pid = fork()) < 0)
    {
        printf("error:fork failed.\n");
        exit(1);
    }
    else if (pid == 0)
    {
        if (execvp(argv[0], argv) < 0 && strcmp(argv[0], "cd"))
            printf("error:invalid command.\n");
        exit(0);
    }
    else
    {
        while (wait(&status) != pid)
            ;
    }
}

//输出重定向
void  execute_file(char** argv, char* output)
{
    pid_t pid;
    int status, flag;
    char* file = NULL;
    if ((pid = fork()) < 0)
    {
        printf("error:fork failed.\n");
        exit(1);
    }
    else if (pid == 0)
    {
        if (strstr(output, ">") > 0)
        {
            char* p = strtok_r(output, ">", &file);
            output += 1;
            file = trim(file);
            flag = 1;
            int old_stdout = dup(1);
            FILE* fp1 = freopen(output, "w+", stdout);
            execute_file(argv, file);
            fclose(stdout);
            FILE* fp2 = fdopen(old_stdout, "w");
            *stdout = *fp2;
            exit(0);
        }
        if (strstr(output, "<") > 0)
        {
            char* p = strtok_r(output, "<", &file);
            file = trim(file);
            flag = 1;
            int fd = open(file, O_RDONLY);
            if (fd < 0)
            {
                printf("No such file or directory.");
                exit(0);
            }
        }
        if (strstr(output, "|") > 0)
        {
            fflush(stdout); printf("here"); fflush(stdout);
            char* p = strtok_r(output, "|", &file);
            file = trim(file);
            flag = 1;
            char* args[64];
            parse(file, args);
            execute(args);
        }
        int old_stdout = dup(1);
        FILE* fp1 = freopen(output, "w+", stdout);
        if (execvp(argv[0], argv) < 0)
            printf("error:in exec");
        fclose(stdout);
        FILE* fp2 = fdopen(old_stdout, "w");
        *stdout = *fp2;
        exit(0);
    }
    else
    {
        while (wait(&status) != pid)
            ;
    }
}


//输入重定向
void  execute_input(char** argv, char* output)
{
    pid_t pid;
    int fd;
    char* file;
    int flag = 0;
    int status;
    if ((pid = fork()) < 0)
    {
        printf("error:fork failed\n");
        exit(1);
    }
    else if (pid == 0)
    {
        if (strstr(output, "<") > 0)
        {
            char* p = strtok_r(output, "<", &file);
            file = trim(file);
            flag = 1;
            fd = open(output, O_RDONLY);
            if (fd < 0)
            {
                printf("No such file or directory.");
                exit(0);
            }
            output = file;
        }
        if (strstr(output, ">") > 0)
        {
            char* p = strtok_r(output, ">", &file);
            file = trim(file);
            flag = 1;
            fflush(stdout);
            fflush(stdout);
            int old_stdout = dup(1);
            FILE* fp1 = freopen(file, "w+", stdout);
            execute_input(argv, output);
            fclose(stdout);
            FILE* fp2 = fdopen(old_stdout, "w");
            *stdout = *fp2;
            exit(0);
        }
        if (strstr(output, "|") > 0)
        {
            char* p = strtok_r(output, "|", &file);
            file = trim(file);
            flag = 1;
            char* args[64];
            parse(file, args);
            int pfds[2];
            pid_t pid, pid2;
            int status, status2;
            pipe(pfds);
            int fl = 0;
            if ((pid = fork()) < 0)
            {
                printf("error:fork failed\n");
                exit(1);
            }
            if ((pid2 = fork()) < 0)
            {
                printf("error:fork failed\n");
                exit(1);
            }
            if (pid == 0 && pid2 != 0)
            {
                close(1);
                dup(pfds[1]);
                close(pfds[0]);
                close(pfds[1]);
                fd = open(output, O_RDONLY);
                close(0);
                dup(fd);
                if (execvp(argv[0], argv) < 0)
                {
                    close(pfds[0]);
                    close(pfds[1]);
                    printf("error:in exec");
                    fl = 1;
                    exit(0);
                }
                close(fd);
                exit(0);
            }
            else if (pid2 == 0 && pid != 0 && fl != 1)
            {
                close(0);
                dup(pfds[0]);
                close(pfds[1]);
                close(pfds[0]);
                if (execvp(args[0], args) < 0)
                {
                    close(pfds[0]);
                    close(pfds[1]);
                    printf("error:in exec");
                    exit(0);
                }
            }
            else
            {
                close(pfds[0]);
                close(pfds[1]);
                while (wait(&status) != pid);
                while (wait(&status2) != pid2);
            }
            exit(0);
        }
        fd = open(output, O_RDONLY);
        close(0);
        dup(fd);
        if (execvp(argv[0], argv) < 0)
        {
            printf("error:in exec");
        }
        close(fd);
        exit(0);
    }
    else
    {
        while (wait(&status) != pid);
    }

}

//单管道
void execute_pipe(char** argv, char* output)
{
    int pfds[2], pf[2], flag;
    char* file;
    pid_t pid, pid2, pid3;
    int status, status2, old_stdout;
    pipe(pfds);
    int blah = 0;
    char* args[64];
    char* argp[64];
    int fl = 0;
    if ((pid = fork()) < 0)
    {
        printf("error:fork failed\n");
        exit(1);
    }
    if ((pid2 = fork()) < 0)
    {
        printf("error:fork failed\n");
        exit(1);
    }
    if (pid == 0 && pid2 != 0)
    {
        close(1);
        dup(pfds[1]);
        close(pfds[0]);
        close(pfds[1]);
        if (execvp(argv[0], argv) < 0)
        {
            close(pfds[0]);
            close(pfds[1]);
            printf("error:in exec");
            fl = 1;
            kill(pid2, SIGUSR1);
            exit(0);
        }
    }
    else if (pid2 == 0 && pid != 0)
    {
        if (fl == 1) { exit(0); }
        if (strstr(output, "<") > 0)
        {
            char* p = strtok_r(output, "<", &file);
            file = trim(file);
            flag = 1;
            parse(output, args);
            execute_input(args, file);
            close(pfds[0]);
            close(pfds[1]);
            exit(0);
        }
        if (strstr(output, ">") > 0)
        {
            char* p = strtok_r(output, ">", &file);
            file = trim(file);
            flag = 1;
            parse(output, args);
            blah = 1;
        }

        else
        {
            parse(output, args);
        }
        close(0);
        dup(pfds[0]);
        close(pfds[1]);
        close(pfds[0]);
        if (blah == 1)
        {
            old_stdout = dup(1);
            FILE* fp1 = freopen(file, "w+", stdout);
        }
        if (execvp(args[0], args) < 0)
        {
            fflush(stdout);
            printf("error:in exec %d", pid);
            kill(pid, SIGUSR1);
            close(pfds[0]);
            close(pfds[1]);
        }
        fflush(stdout);
        printf("HERE");
        if (blah == 1)
        {
            fclose(stdout);
            FILE* fp2 = fdopen(old_stdout, "w");
            *stdout = *fp2;
        }
    }
    else
    {
        close(pfds[0]);
        close(pfds[1]);
        while (wait(&status) != pid);
        while (wait(&status2) != pid2);
    }
}

//多管道
void execute_pipe2(char** argv, char** args, char** argp)
{
    int status;
    int i;
    int pipes[4];
    pipe(pipes);
    pipe(pipes + 2);
    if (fork() == 0)
    {
        dup2(pipes[1], 1);
        close(pipes[0]);
        close(pipes[1]);
        close(pipes[2]);
        close(pipes[3]);
        if (execvp(argv[0], argv) < 0)
        {
            fflush(stdout);
            printf("error:in exec");
            fflush(stdout);
            close(pipes[0]);
            close(pipes[1]);
            close(pipes[2]);
            close(pipes[3]);
            exit(1);
        }
    }
    else
    {
        if (fork() == 0)
        {
            dup2(pipes[0], 0);
            dup2(pipes[3], 1);
            close(pipes[0]);
            close(pipes[1]);
            close(pipes[2]);
            close(pipes[3]);
            if (execvp(args[0], args) < 0)
            {
                fflush(stdout);
                printf("error:in exec");
                fflush(stdout);
                close(pipes[0]);
                close(pipes[1]);
                close(pipes[2]);
                close(pipes[3]);
                exit(1);
            }
        }
        else
        {
            if (fork() == 0)
            {
                dup2(pipes[2], 0);
                close(pipes[0]);
                close(pipes[1]);
                close(pipes[2]);
                close(pipes[3]);
                if (execvp(argp[0], argp) < 0)
                {
                    fflush(stdout);
                    printf("error:in exec");
                    fflush(stdout);
                    close(pipes[0]);
                    close(pipes[1]);
                    close(pipes[2]);
                    close(pipes[3]);
                    exit(1);
                }
            }
        }
    }
    close(pipes[0]);
    close(pipes[1]);
    close(pipes[2]);
    close(pipes[3]);
    for (i = 0; i < 3; i++)
        wait(&status);
}

// 显示历史命令函数
void show_history()
{
    int i; // 循环变量（C89兼容性要求）
    printf("Command History:\n");
    int count = (filled < hist_size) ? filled : hist_size;
    int start = (filled < hist_size) ? 0 : (head + 1) % hist_size;

    // 遍历并显示所有历史命令
    for (i = 0; i < count; i++)
    {
        int index = (start + i) % hist_size;
        printf("%d: %s\n", i + 1, hist[index]);
    }
}

// 执行历史命令函数
void execute_history_command(int index)
{
    // 检查索引是否有效
    if (index < 1 || index >((filled < hist_size) ? filled : hist_size))
    {
        printf("Invalid history index\n");
        return;
    }

    // 计算实际索引位置
    int actual_index;
    if (filled < hist_size)
    {
        actual_index = index - 1;
    }
    else
    {
        actual_index = (head + index) % hist_size;
    }

    printf("Executing: %s\n", hist[actual_index]);

    // 复制历史命令到临时缓冲区
    char line[1024];
    strcpy(line, hist[actual_index]);

    // 解析并执行历史命令
    char* argv[64];
    parse(line, argv);
    execute(argv);
}

// 主函数
int main()
{
    char line[1024];
    char* argv[64];
    char* args[64];
    char* left;
    size_t size = 0;
    char ch;
    int count = 0;
    char* tri;
    char* second;
    char* file;
    int i; // 循环变量（C89兼容性要求）

    // 初始化历史记录数组
    for (i = 0; i < hist_size; i++)
    {
        hist[i] = (char*)malloc(150);
    }

    // 主循环
    while (1)
    {
        count = 0;
        int flag = 0;
        char* word = NULL;
        char* dire[] = { "pwd" };

        fflush(stdout);
        printf("SHELL~");
        fflush(stdout);
        execute(dire); // 显示当前目录
        printf("$");

        // 获取用户输入
        int len = getline(&word, &size, stdin);

        // 跳过空行
        if (*word == '\n')
            continue;

        word[len - 1] = '\0'; // 去除换行符

        // 处理history命令
        if (strcmp(word, "history") == 0)
        {
            show_history();
            continue;
        }
        // 处理!n格式的历史命令调用
        else if (word[0] == '!' && isdigit(word[1]))
        {
            int index = atoi(&word[1]);
            execute_history_command(index);
            continue;
        }

        file = NULL;
        i = 0;
        char* temp = (char*)malloc(150);
        strcpy(temp, word);
        parse(temp, argv);

        // 将命令添加到历史记录
        strcpy(hist[head], word);
        head = (head + 1) % hist_size;
        if (filled < hist_size) filled++;

        // 检查命令中是否包含重定向或管道符号
        for (i = 0; word[i] != '\0'; i++)
        {
            if (word[i] == '>') // 输出重定向
            {
                char* p = strtok_r(word, ">", &file);
                file = trim(file);
                flag = 1;
                break;
            }
            else if (word[i] == '<') // 输入重定向
            {
                char* p = strtok_r(word, "<", &file);
                file = trim(file);
                flag = 2;
                break;
            }
            else if (word[i] == '|') // 管道
            {
                char* p = strtok_r(word, "|", &left);
                flag = 3;
                break;
            }
        }

        // 处理exit命令
        if (strcmp(word, "exit") == 0)
        {
            exit(0);
        }

        // 根据检测到的符号类型执行相应操作
        if (flag == 1) // 输出重定向
        {
            parse(word, argv);
            execute_file(argv, file);
        }
        else if (flag == 2) // 输入重定向
        {
            parse(word, argv);
            execute_input(argv, file);
        }
        else if (flag == 3) // 管道
        {
            char* argp[64];
            char* output, * file;

            // 处理多个管道
            if (strstr(left, "|") > 0)
            {
                char* p = strtok_r(left, "|", &file);
                parse(word, argv);
                parse(left, args);
                parse(file, argp);
                execute_pipe2(argv, args, argp);
            }
            else // 单个管道
            {
                parse(word, argv);
                execute_pipe(argv, left);
            }
        }
        else // 普通命令
        {
            parse(word, argv);
            execute(argv);
        }
    }

    return 0;
}