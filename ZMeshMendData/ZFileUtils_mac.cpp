// Minimal ZFileUtils replacement for ZMeshMend on macOS.
// Implements only the ZScript FileExecute entry points used by ZMeshMend.

#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <sys/stat.h>
#include <spawn.h>
#include <unistd.h>
#include <vector>

extern char** environ;

static const int kMemBlockSafeSize = 4096;

static bool has_text(const char* value)
{
    return value != nullptr && value[0] != '\0';
}

static std::string read_mem_string(const char* mem)
{
    if (!mem)
        return std::string();
    return std::string(mem);
}

static std::string normalize_zbrush_path(const std::string& path)
{
    if (path.size() >= 3 && path[0] == '!' && path[1] == ':' && path[2] == '/')
        return path.substr(2);
    return path;
}

static std::string parent_dir(const std::string& path)
{
    size_t slash = path.find_last_of('/');
    if (slash == std::string::npos)
        return std::string();
    if (slash == 0)
        return "/";
    return path.substr(0, slash);
}

extern "C" __attribute__((visibility("default")))
float Version(const char*, double, char*, char*)
{
    return 8.0f;
}

extern "C" __attribute__((visibility("default")))
float FileDelete(const char* path, double, char*, char*)
{
    if (!has_text(path))
        return 1.0f;

    const std::string normalized = normalize_zbrush_path(path);
    if (unlink(normalized.c_str()) == 0 || errno == ENOENT)
        return 0.0f;

    return static_cast<float>(errno);
}

extern "C" __attribute__((visibility("default")))
float FileRename(const char* fromPath, double, char* toPathMem, char* altToPathMem)
{
    if (!has_text(fromPath))
        return 1.0f;

    std::string toPath = read_mem_string(toPathMem);
    if (toPath.empty())
        toPath = read_mem_string(altToPathMem);
    if (toPath.empty())
        return 1.0f;

    const std::string normalizedFrom = normalize_zbrush_path(fromPath);
    const std::string normalizedTo = normalize_zbrush_path(toPath);
    if (rename(normalizedFrom.c_str(), normalizedTo.c_str()) == 0)
        return 0.0f;

    return static_cast<float>(errno);
}

extern "C" __attribute__((visibility("default")))
float FileRead(const char* path, double, char* outMem, char* altOutMem)
{
    if (!has_text(path))
        return 1.0f;

    char* dst = outMem ? outMem : altOutMem;
    if (!dst)
        return 1.0f;

    const std::string normalized = normalize_zbrush_path(path);
    FILE* file = fopen(normalized.c_str(), "rb");
    if (!file)
        return static_cast<float>(errno);

    size_t n = fread(dst, 1, kMemBlockSafeSize - 1, file);
    dst[n] = '\0';
    fclose(file);
    return 0.0f;
}

extern "C" __attribute__((visibility("default")))
float LaunchAppWithFile(const char* filePath, double, char* appPathMem, char* altAppPathMem)
{
    if (!has_text(filePath))
        return 1.0f;

    std::string appPath = read_mem_string(appPathMem);
    if (appPath.empty())
        appPath = read_mem_string(altAppPathMem);

    std::string fileArg = normalize_zbrush_path(filePath);
    std::string executable = appPath.empty() ? fileArg : normalize_zbrush_path(appPath);
    const std::string cwd = parent_dir(executable);

    posix_spawn_file_actions_t actions;
    posix_spawn_file_actions_init(&actions);
    if (!cwd.empty())
        posix_spawn_file_actions_addchdir_np(&actions, cwd.c_str());

    std::vector<char*> argv;
    argv.push_back(const_cast<char*>(executable.c_str()));
    if (!appPath.empty())
        argv.push_back(const_cast<char*>(fileArg.c_str()));
    argv.push_back(nullptr);

    pid_t pid = 0;
    int err = posix_spawn(&pid, executable.c_str(), &actions, nullptr, argv.data(), environ);
    posix_spawn_file_actions_destroy(&actions);
    if (err != 0)
        return static_cast<float>(err);

    return 0.0f;
}
