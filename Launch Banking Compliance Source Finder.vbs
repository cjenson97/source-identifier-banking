Option Explicit

Dim shell, fso, scriptDir, cmdPath
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
cmdPath = Chr(34) & scriptDir & "\Launch Banking Compliance Source Finder.cmd" & Chr(34)

shell.Run cmdPath, 0, False
