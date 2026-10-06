#Requires AutoHotkey v2.0
#SingleInstance Force

flameshot := "C:\Program Files\Flameshot\bin\flameshot.exe"

PrintScreen::Run '"' flameshot '" gui'
