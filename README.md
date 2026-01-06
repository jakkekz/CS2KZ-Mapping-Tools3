# CS2KZ Mapping Tools (C# Edition)

A smooth, native Windows application for CS2KZ mapping tools built with C# WinForms and .NET 8.

## Features

- **Native Performance**: No Python interpreter overhead, instant UI response
- **Custom Dark Theme System**: Multiple themes (Grey, Black, White, Pink, Orange, Blue, Red, Green, Yellow, Dracula)
- **Custom Title Bar**: Frameless window with drag-to-move functionality
- **Button Grid Layout**: Clean, organized interface for launching tools
- **Settings Persistence**: JSON-based settings for themes, window position, button visibility
- **Mixed Implementation**: Native C# forms for core tools, Python integration for specialized scripts
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
CS2KZ-Mapping-Tools-3/
├── Program.cs                    # Entry point
├── MainForm.cs                   # Main window with custom title bar
├── CustomButton.cs               # Custom button control
├── ThemeManager.cs               # Theme system
├── SettingsManager.cs            # Settings persistence
├── VTF2PNGForm.cs                # Native VTF to PNG converter
├── PointWorldTextDialog.cs       # Native point_worldtext generator
├── PointWorldTextManager.cs      # Text generation engine
├── LoadingScreenForm.cs          # Native loading screen generator
├── CS2KZMappingTools.csproj      # Project file
├── CS2KZMappingTools.sln         # Solution file
├── icons/                        # Icon files
├── chars/                        # Character images for text generation
├── fonts/                        # Font files
├── scripts/                      # Python scripts (legacy)
├── utils/                        # Utility files
└── porting/                      # Map porting tools
```

## Implemented Tools

### Native C# Implementations
- **VTF to PNG Converter**: Full GUI with automatic VTFCmd.exe download and batch conversion
- **Point World Text Generator**: CS2 addon detection with character preview
- **Loading Screen Generator**: Skybox and text overlay creation

### Python Script Integration
- **Skybox Converter**: Python-based skybox processing
- **Sound Tools**: Audio file management
- **Map Porting**: CS2 map import/export
- **Source2Viewer Updater**: Tool management

## Migrating from Python Version

This C# version enhances the existing Python tools:
- Core tools rewritten in C# for better performance and reliability
- Python scripts remain available for specialized functionality
- GUI executables are launched as subprocesses where needed
- Settings are stored in the same location (`%TEMP%\.CS2KZ-mapping-tools`)
- Automatic dependency management for external tools (VTFCmd.exe, etc.)