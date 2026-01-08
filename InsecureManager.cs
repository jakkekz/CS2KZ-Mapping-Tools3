using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Threading.Tasks;
using Microsoft.Win32;

namespace CS2KZMappingTools
{
    public class InsecureManager
    {
        private const string STEAM_REGISTRY_KEY = @"Software\Valve\Steam";

        public event Action<string>? LogMessage;
        public event Action<string>? LogEvent;

        private void Log(string message)
        {
            LogMessage?.Invoke(message);
            LogEvent?.Invoke(message);
        }

        public Task<string?> GetSteamDirectoryAsync()
        {
            try
            {
                using var key = Registry.CurrentUser.OpenSubKey(STEAM_REGISTRY_KEY);
                if (key?.GetValue("SteamPath") is string steamPath)
                {
                    return Task.FromResult<string?>(steamPath);
                }
            }
            catch (Exception ex)
            {
                Log($"Error accessing Steam registry: {ex.Message}");
            }
            
            Log("Steam is not installed or the registry key was not found.");
            return Task.FromResult<string?>(null);
        }

        public async Task<string?> FindCS2LibraryPathAsync(string libraryFoldersPath)
        {
            if (!File.Exists(libraryFoldersPath))
            {
                Log($"libraryfolders.vdf not found at {libraryFoldersPath}");
                return null;
            }

            try
            {
                var content = await File.ReadAllTextAsync(libraryFoldersPath, Encoding.UTF8);
                Log($"Successfully read libraryfolders.vdf ({content.Length} characters)");
                
                var parser = new VdfParser();
                var libraryData = parser.Parse(content);
                Log($"Parsed VDF data, found {libraryData.Count} root keys");
                
                // First try the nested structure (newer Steam format)
                if (libraryData.TryGetValue("libraryfolders", out var foldersObj) && foldersObj is Dictionary<string, object> folders)
                {
                    Log($"Found libraryfolders section with {folders.Count} entries");
                    
                    foreach (var kvp in folders)
                    {
                        Log($"Checking library folder: {kvp.Key}");
                        
                        if (kvp.Value is Dictionary<string, object> folder)
                        {
                            // Check if this folder has apps and contains CS2 (appid 730)
                            if (folder.TryGetValue("apps", out var appsObj) && appsObj is Dictionary<string, object> apps)
                            {
                                Log($"  Found apps section with {apps.Count} apps");
                                
                                if (apps.ContainsKey("730"))
                                {
                                    if (folder.TryGetValue("path", out var pathObj) && pathObj is string path)
                                    {
                                        Log($"  Found CS2 in library: {path}");
                                        return path;
                                    }
                                    else
                                    {
                                        Log($"  Found CS2 but no path in folder data");
                                    }
                                }
                                else
                                {
                                    Log($"  CS2 (730) not found in this library");
                                }
                            }
                            else
                            {
                                Log($"  No apps section found in folder");
                            }
                        }
                    }
                }
                else
                {
                    // Try flat structure (older Steam format) - each numbered entry is a library folder
                    Log($"No libraryfolders section found, trying flat structure. Root keys: {string.Join(", ", libraryData.Keys)}");
                    
                    // Check Steam default location first
                    var steamPath = await GetSteamDirectoryAsync();
                    if (!string.IsNullOrEmpty(steamPath))
                    {
                        var defaultManifestPath = Path.Combine(steamPath, "steamapps", "appmanifest_730.acf");
                        if (!File.Exists(defaultManifestPath))
                        {
                            defaultManifestPath = Path.Combine(steamPath, "SteamApps", "appmanifest_730.acf");
                        }
                        
                        if (File.Exists(defaultManifestPath))
                        {
                            Log($"Found CS2 in default Steam library: {steamPath}");
                            return steamPath;
                        }
                    }
                    
                    // Check all library paths in the VDF
                    foreach (var kvp in libraryData)
                    {
                        // Skip non-path entries (like contentid, label, etc.)
                        if (kvp.Value is string libraryPath && Directory.Exists(libraryPath))
                        {
                            Log($"Checking library path: {libraryPath}");
                            
                            // Try both casings for steamapps folder
                            var manifestPath = Path.Combine(libraryPath, "steamapps", "appmanifest_730.acf");
                            if (!File.Exists(manifestPath))
                            {
                                manifestPath = Path.Combine(libraryPath, "SteamApps", "appmanifest_730.acf");
                            }
                            
                            if (File.Exists(manifestPath))
                            {
                                Log($"Found CS2 in library: {libraryPath}");
                                return libraryPath;
                            }
                        }
                    }
                    
                    Log("CS2 not found in any library path");
                }
            }
            catch (Exception ex)
            {
                Log($"Error parsing libraryfolders.vdf: {ex.Message}");
            }
            
            Log("Failed to find CS2 library path.");
            return null;
        }

        public async Task<string?> GetCS2PathAsync()
        {
            var steamPath = await GetSteamDirectoryAsync();
            if (steamPath == null)
            {
                Log("Failed to get Steam directory");
                return null;
            }
            Log($"Steam directory: {steamPath}");

            // Try both casings for libraryfolders.vdf
            var libraryFoldersPath = Path.Combine(steamPath, "steamapps", "libraryfolders.vdf");
            if (!File.Exists(libraryFoldersPath))
            {
                libraryFoldersPath = Path.Combine(steamPath, "SteamApps", "libraryfolders.vdf");
            }
            
            var libraryPath = await FindCS2LibraryPathAsync(libraryFoldersPath);
            if (libraryPath == null)
            {
                Log("Failed to get library path");
                return null;
            }
            Log($"Library path: {libraryPath}");

            try
            {
                // Try both casings (steamapps and SteamApps)
                var manifestPath = Path.Combine(libraryPath, "steamapps", "appmanifest_730.acf");
                if (!File.Exists(manifestPath))
                {
                    manifestPath = Path.Combine(libraryPath, "SteamApps", "appmanifest_730.acf");
                }
                
                Log($"Looking for CS2 manifest at: {manifestPath}");
                
                if (!File.Exists(manifestPath))
                {
                    Log($"CS2 manifest not found at {manifestPath}");
                    return null;
                }

                Log("Reading CS2 manifest...");
                var content = await File.ReadAllTextAsync(manifestPath, Encoding.UTF8);
                Log($"Manifest content length: {content.Length} characters");
                Log($"First 200 chars of manifest: {content.Substring(0, Math.Min(200, content.Length))}");
                
                var parser = new VdfParser();
                var data = parser.Parse(content);
                
                Log($"Parsed manifest data, found {data.Count} root keys");
                foreach (var rootKey in data.Keys)
                {
                    Log($"Manifest root key: '{rootKey}'");
                }

                // First try to get installdir directly from root level (flat structure)
                if (data.TryGetValue("installdir", out var installdirObj) && installdirObj is string installdir)
                {
                    Log($"Found install directory at root level: '{installdir}'");
                    
                    // Try both casings for steamapps folder
                    var cs2Path = Path.Combine(libraryPath, "steamapps", "common", installdir);
                    if (!Directory.Exists(cs2Path))
                    {
                        cs2Path = Path.Combine(libraryPath, "SteamApps", "common", installdir);
                    }
                    
                    Log($"Final CS2 path: {cs2Path}");
                    return cs2Path;
                }
                
                // Fallback: try nested AppState structure
                if (data.TryGetValue("AppState", out var appStateObj) && appStateObj is Dictionary<string, object> appState)
                {
                    Log($"Found AppState section with {appState.Count} keys");
                    foreach (var key in appState.Keys)
                    {
                        Log($"AppState key: '{key}' = '{appState[key]}'");
                    }
                    
                    if (appState.TryGetValue("installdir", out var nestedInstalldirObj) && nestedInstalldirObj is string nestedInstalldir)
                    {
                        Log($"Found install directory in AppState: '{nestedInstalldir}'");
                        
                        // Try both casings for steamapps folder
                        var cs2Path = Path.Combine(libraryPath, "steamapps", "common", nestedInstalldir);
                        if (!Directory.Exists(cs2Path))
                        {
                            cs2Path = Path.Combine(libraryPath, "SteamApps", "common", nestedInstalldir);
                        }
                        
                        Log($"Final CS2 path: {cs2Path}");
                        return cs2Path;
                    }
                    else
                    {
                        Log("No 'installdir' key found in AppState or it's not a string");
                    }
                }
                else
                {
                    Log("No 'AppState' section found and no root-level installdir found");
                }

                Log("Failed to parse CS2 manifest or find install directory");
                return null;
            }
            catch (Exception ex)
            {
                Log($"Error reading CS2 manifest: {ex.Message}");
                return null;
            }
        }

        public async Task RunInsecureModeAsync()
        {
            try
            {
                Log("Starting CS2 in insecure mode...");
                
                var cs2Path = await GetCS2PathAsync();
                if (cs2Path == null)
                {
                    Log("Failed to get CS2 path. Closing in 3 seconds...");
                    await Task.Delay(3000);
                    return;
                }

                Log($"Found CS2 at: {cs2Path}");
                
                var cs2ExePath = Path.Combine(cs2Path, "game", "bin", "win64", "cs2.exe");
                if (!File.Exists(cs2ExePath))
                {
                    Log($"CS2 executable not found at {cs2ExePath}");
                    Log("Closing in 3 seconds...");
                    await Task.Delay(3000);
                    return;
                }
                
                await RunCS2InsecureAsync(cs2ExePath);
                
                Log("✓ CS2 insecure mode session completed successfully");
            }
            catch (Exception ex)
            {
                Log($"Error in insecure mode process: {ex.Message}");
                throw;
            }
        }

        private async Task RunCS2InsecureAsync(string cs2ExePath)
        {
            Log("Launching CS2 in insecure mode...");
            
            var processInfo = new ProcessStartInfo
            {
                FileName = cs2ExePath,
                Arguments = "-insecure",
                UseShellExecute = false,
                CreateNoWindow = false
            };

            using var process = Process.Start(processInfo);
            if (process != null)
            {
                Log($"CS2 started in insecure mode with PID {process.Id}");
                await process.WaitForExitAsync();
                Log("CS2 insecure mode process has ended");
            }
            else
            {
                throw new InvalidOperationException("Failed to start CS2 in insecure mode");
            }
        }
    }
}