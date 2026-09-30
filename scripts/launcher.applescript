on run
    set appPath to POSIX path of (path to me)
    set projectPath to do shell script "/usr/bin/dirname " & quoted form of appPath
    try
        set nodePath to "__NODE_PATH__"
        do shell script quoted form of nodePath & " " & quoted form of (projectPath & "/scripts/start.mjs")
    on error messageText
        display dialog messageText with title "Codex 项目资料" buttons {"好"} default button "好"
    end try
end run
