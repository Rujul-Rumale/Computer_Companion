' Launch COMPUTER Companion without any console window
Set shell = CreateObject("WScript.Shell")
shell.Run "powershell -ExecutionPolicy Bypass -File launch_companion.ps1", 0, False
