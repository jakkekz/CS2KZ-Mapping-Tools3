# CS2KZ Mapping Tools (C# Edition)

A smooth, native Windows application for CS2KZ mapping tools built with C# WinForms and .NET 8.

## Features

- **Native Performance**: No Python interpreter overhead, instant UI response
- **Custom Dark Theme System**: Multiple themes (Grey, Black, White, Pink, Orange, Blue, Red, Green, Yellow, Dracula)
- **Custom Title Bar**: Frameless window with drag-to-move functionality
- **Button Grid Layout**: Clean, organized interface for launching tools
- **Settings Persistence**: JSON-based settings for themes, window position, button visibility
- **Python Integration**: Launches existing Python scripts seamlessly
- **Always on Top**: Optional window pinning
- **Window Opacity Control**: Adjustable transparency

## Requirements

- .NET 8.0 Runtime (Windows)
- Windows 10/11

## Building

```bash
dotnet restore
dotnet build
```

## Running

```bash
dotnet run
```

Or use Visual Studio 2022 to open `CS2KZMappingTools.sln`

## Project Structure

```
CS2KZ-Mapping-Tools-2/
├── Program.cs              # Entry point
├── MainForm.cs             # Main window with custom title bar
├── CustomButton.cs         # Custom button control
├── ThemeManager.cs         # Theme system
├── SettingsManager.cs      # Settings persistence
├── CS2KZMappingTools.csproj # Project file
├── CS2KZMappingTools.sln   # Solution file
├── icons/                  # Icon files
├── gui_tools/              # Python GUI executables
├── scripts/                # Python scripts
└── utils/                  # Utility files
```

## Migrating from Python Version

This C# version maintains compatibility with the existing Python tools:
- All Python scripts remain unchanged
- GUI executables are launched as subprocesses
- Settings are stored in the same location (`%TEMP%\.CS2KZ-mapping-tools`)