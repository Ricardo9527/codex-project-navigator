on run
    set appPath to POSIX path of (path to me)
    set projectPath to do shell script "/usr/bin/dirname " & quoted form of appPath
    try
        set nodePath to "__NODE_PATH__"
        do shell script quoted form of nodePath & " " & quoted form of (projectPath & "/scripts/start.mjs")
    on error messageText number errorNumber
        if errorNumber is 3 then
            display dialog messageText with title "Codex 已启动，图标动画未完成" buttons {"好"} default button "好"
        else
            display dialog messageText with title "Codex 项目资料" buttons {"好"} default button "好"
        end if
    end try
end run
