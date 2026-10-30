Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
WshShell.Run "python """ & scriptDir & "\gemini_helper.py""", 0, False
Set WshShell = Nothing
Set fso = Nothing
