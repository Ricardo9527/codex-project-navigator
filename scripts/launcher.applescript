on run
    set appPath to POSIX path of (path to me)
    set projectPath to do shell script "/usr/bin/dirname " & quoted form of appPath
    try
        do shell script "/opt/homebrew/bin/node " & quoted form of (projectPath & "/scripts/start.mjs")
    on error messageText
        display dialog messageText with title "Codex 项目资料" buttons {"好"} default button "好"
    end try
end run
