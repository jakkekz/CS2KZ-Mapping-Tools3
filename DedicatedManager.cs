using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Net.Http;
using System.Text;
using System.Threading.Tasks;
using Microsoft.Win32;

namespace CS2KZMappingTools
{
    public class DedicatedManager
    {
        private static readonly HttpClient httpClient = new HttpClient();
        private const string STEAM_REGISTRY_KEY = @"Software\Valve\Steam";
        private const string GAMETRACKING_BASE_URL = "https://raw.githubusercontent.com/SteamDatabase/GameTracking-CS2/refs/heads/master/";
        private static readonly string TEMP_FOLDER = Path.Combine(Path.GetTempPath(), ".CS2KZ-mapping-tools");
        private static readonly string ORIGINAL_FILES_FOLDER = Path.Combine(TEMP_FOLDER, "original files");

        public event Action<string>? LogMessage;
        public event Action<string>? LogEvent;
#pragma warning disable CS0067 // The events are declared but never used
        public event Action<int, int>? ProgressUpdated;
        public event Action? ProgressIndeterminate;
#pragma warning restore CS0067

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

        private async Task DownloadOriginalFilesAsync()
        {
            try
            {
                Log("Downloading original gameinfo files from GitHub...");
                
                Directory.CreateDirectory(ORIGINAL_FILES_FOLDER);
                
                var filesToDownload = new[]
                {
                    "game/csgo/gameinfo.gi",
                    "game/csgo_core/gameinfo.gi"
                };
                
                foreach (var filePath in filesToDownload)
                {
                    var url = GAMETRACKING_BASE_URL + filePath;
                    var localPath = Path.Combine(ORIGINAL_FILES_FOLDER, Path.GetFileName(filePath));
                    
                    if (filePath.Contains("csgo_core"))
                    {
                        localPath = Path.Combine(ORIGINAL_FILES_FOLDER, "gameinfo_core.gi");
                    }
                    
                    try
                    {
                        Log($"Downloading {filePath}...");
                        var response = await httpClient.GetAsync(url);
                        response.EnsureSuccessStatusCode();
                        
                        var content = await response.Content.ReadAsStringAsync();
                        content = content.Replace("\n", "\r\n");
                        
                        await File.WriteAllTextAsync(localPath, content);
                        Log($"✓ Downloaded {Path.GetFileName(localPath)}");
                    }
                    catch (Exception ex)
                    {
                        Log($"✗ Failed to download {filePath}: {ex.Message}");
                    }
                }
                
                Log("✓ Original files download complete");
            }
            catch (Exception ex)
            {
                Log($"Error downloading original files: {ex.Message}");
            }
        }

        public async Task RunDedicatedServerProcessAsync()
        {
            try
            {
                Log("Starting CS2 Dedicated Server setup and launch...");
                
                await DownloadOriginalFilesAsync();
                
                var cs2Path = await GetCS2PathAsync();
                if (cs2Path == null)
                {
                    Log("Failed to get CS2 path. Cannot continue.");
                    return;
                }

                var (gameInfoPath, backupPath, coreGameInfoPath, coreBackupPath) = await BackupAndModifyGameInfoAsync(cs2Path);
                
                try
                {
                    var cs2ExePath = Path.Combine(cs2Path, "game", "bin", "win64", "cs2.exe");
                    if (!File.Exists(cs2ExePath))
                    {
                        throw new FileNotFoundException($"CS2 executable not found at {cs2ExePath}");
                    }
                    
                    await RunDedicatedServerAsync(cs2ExePath);
                }
                finally
                {
                    Log("CS2 dedicated server process has ended. Restoring gameinfo files to original state...");
                    await VerifyGameInfoAsync(cs2Path);
                    
                    try
                    {
                        if (File.Exists(backupPath)) File.Delete(backupPath);
                        if (File.Exists(coreBackupPath)) File.Delete(coreBackupPath);
                        Log("✓ Cleanup completed");
                    }
                    catch (Exception cleanupEx)
                    {
                        Log($"Note: Could not clean up backup files: {cleanupEx.Message}");
                    }
                }
                
                Log("✓ Dedicated server process completed successfully");
            }
            catch (Exception ex)
            {
                Log($"Error in dedicated server process: {ex.Message}");
                throw;
            }
        }

        private async Task<(string gameInfoPath, string backupPath, string coreGameInfoPath, string coreBackupPath)> BackupAndModifyGameInfoAsync(string cs2Path)
        {
            var gameInfoPath = Path.Combine(cs2Path, "game", "csgo", "gameinfo.gi");
            var backupPath = Path.Combine(cs2Path, "game", "csgo", "gameinfo.gi.bak");
            var coreGameInfoPath = Path.Combine(cs2Path, "game", "csgo_core", "gameinfo.gi");
            var coreBackupPath = Path.Combine(cs2Path, "game", "csgo_core", "gameinfo.gi.bak");

            Log("Creating backup of gameinfo files...");
            File.Copy(gameInfoPath, backupPath, true);
            File.Copy(coreGameInfoPath, coreBackupPath, true);
            Log("✓ Files backed up");

            await ModifyGameInfoAsync(gameInfoPath, coreGameInfoPath);

            return (gameInfoPath, backupPath, coreGameInfoPath, coreBackupPath);
        }

        private async Task ModifyGameInfoAsync(string gameInfoPath, string coreGameInfoPath)
        {
            Log("Modifying gameinfo files for dedicated server...");
            
            // Modify main gameinfo.gi
            var gameInfoLines = await File.ReadAllLinesAsync(gameInfoPath);
            var gameInfoModified = false;
            
            for (int i = 0; i < gameInfoLines.Length; i++)
            {
                var line = gameInfoLines[i].Trim();
                if (line.StartsWith("Game") && line.Contains("csgo"))
                {
                    if (i + 1 < gameInfoLines.Length && !gameInfoLines[i + 1].Trim().Contains("addons/metamod"))
                    {
                        var indentMatch = System.Text.RegularExpressions.Regex.Match(gameInfoLines[i + 1], @"^(\s*)");
                        var indent = indentMatch.Success ? indentMatch.Groups[1].Value : "\t\t\t";
                        
                        Array.Resize(ref gameInfoLines, gameInfoLines.Length + 1);
                        Array.Copy(gameInfoLines, i + 1, gameInfoLines, i + 2, gameInfoLines.Length - i - 2);
                        gameInfoLines[i + 1] = $"{indent}Game\tcsgo/addons/metamod";
                        gameInfoModified = true;
                        break;
                    }
                }
            }

            if (gameInfoModified)
            {
                await File.WriteAllLinesAsync(gameInfoPath, gameInfoLines);
                Log("✓ Main gameinfo.gi modified");
            }

            // Modify core gameinfo.gi 
            var coreGameInfoLines = await File.ReadAllLinesAsync(coreGameInfoPath);
            var coreGameInfoModified = false;
            
            for (int i = 0; i < coreGameInfoLines.Length; i++)
            {
                var line = coreGameInfoLines[i].Trim();
                if (line.StartsWith("Game") && line.Contains("csgo"))
                {
                    if (i + 1 < coreGameInfoLines.Length && !coreGameInfoLines[i + 1].Trim().Contains("addons/metamod"))
                    {
                        var indentMatch = System.Text.RegularExpressions.Regex.Match(coreGameInfoLines[i + 1], @"^(\s*)");
                        var indent = indentMatch.Success ? indentMatch.Groups[1].Value : "\t\t\t";
                        
                        Array.Resize(ref coreGameInfoLines, coreGameInfoLines.Length + 1);
                        Array.Copy(coreGameInfoLines, i + 1, coreGameInfoLines, i + 2, coreGameInfoLines.Length - i - 2);
                        coreGameInfoLines[i + 1] = $"{indent}Game\tcsgo/addons/metamod";
                        coreGameInfoModified = true;
                        break;
                    }
                }
            }

            if (coreGameInfoModified)
            {
                await File.WriteAllLinesAsync(coreGameInfoPath, coreGameInfoLines);
                Log("✓ Core gameinfo.gi modified");
            }

            // Add P2P networking modification to main gameinfo
            await ModifyGameInfoP2PAsync(gameInfoPath);
        }

        private async Task ModifyGameInfoP2PAsync(string gameInfoPath)
        {
            Log("Adding P2P networking for dedicated server...");
            
            var lines = await File.ReadAllLinesAsync(gameInfoPath);
            bool modified = false;
            
            for (int i = 0; i < lines.Length; i++)
            {
                var line = lines[i].Trim();
                if (line == "\"FileSystem\"" && i + 1 < lines.Length && lines[i + 1].Trim() == "{")
                {
                    // Find the end of FileSystem block
                    int j = i + 2;
                    int braceCount = 1;
                    while (j < lines.Length && braceCount > 0)
                    {
                        if (lines[j].Trim() == "{") braceCount++;
                        else if (lines[j].Trim() == "}") braceCount--;
                        j++;
                    }
                    
                    // Insert P2P line before the closing brace
                    if (j > i + 2)
                    {
                        var indentMatch = System.Text.RegularExpressions.Regex.Match(lines[i + 2], @"^(\s*)");
                        var indent = indentMatch.Success ? indentMatch.Groups[1].Value : "\t";
                        
                        Array.Resize(ref lines, lines.Length + 1);
                        Array.Copy(lines, j - 1, lines, j, lines.Length - j);
                        lines[j - 1] = $"{indent}\"EnableP2PNetworkingForDedicatedServers\"\t\"1\"";
                        modified = true;
                        break;
                    }
                }
            }
            
            if (modified)
            {
                await File.WriteAllLinesAsync(gameInfoPath, lines);
                Log("✓ P2P networking enabled for dedicated server");
            }
        }

        private async Task RunDedicatedServerAsync(string cs2ExePath)
        {
            Log("Launching CS2 dedicated server...");
            
            var processInfo = new ProcessStartInfo
            {
                FileName = cs2ExePath,
                Arguments = "-dedicated +map de_dust2",
                UseShellExecute = false,
                CreateNoWindow = false
            };

            using var process = Process.Start(processInfo);
            if (process != null)
            {
                Log($"CS2 dedicated server started with PID {process.Id}");
                await process.WaitForExitAsync();
                Log("CS2 dedicated server process has ended");
            }
            else
            {
                throw new InvalidOperationException("Failed to start CS2 dedicated server process");
            }
        }

        private async Task VerifyGameInfoAsync(string cs2Path)
        {
            try
            {
                Log("Restoring gameinfo files from Steam database...");
                Log($"Found CS2 at: {cs2Path}");
                
                var filePaths = new[]
                {
                    "game/csgo/gameinfo.gi",
                    "game/csgo_core/gameinfo.gi",
                    "game/bin/sdkenginetools.txt",
                    "game/bin/assettypes_common.txt"
                };
                
                int filesRestored = 0;
                int filesFailed = 0;
                
                foreach (var filePath in filePaths)
                {
                    var url = GAMETRACKING_BASE_URL + filePath;
                    var fullPath = Path.Combine(cs2Path, filePath);
                    
                    try
                    {
                        Log($"Downloading {filePath}...");
                        var response = await httpClient.GetAsync(url, HttpCompletionOption.ResponseContentRead);
                        
                        if (response.StatusCode != System.Net.HttpStatusCode.OK)
                        {
                            Log($"✗ Failed to download {filePath} (HTTP {(int)response.StatusCode})");
                            filesFailed++;
                            continue;
                        }
                        
                        var contentBytes = await response.Content.ReadAsByteArrayAsync();
                        var content = Encoding.UTF8.GetString(contentBytes).Replace("\n", "\r\n");
                        
                        Directory.CreateDirectory(Path.GetDirectoryName(fullPath)!);
                        await File.WriteAllBytesAsync(fullPath, Encoding.UTF8.GetBytes(content));
                        
                        Log($"✓ Restored {filePath}");
                        filesRestored++;
                    }
                    catch (Exception ex)
                    {
                        Log($"✗ Error restoring {filePath}: {ex.Message}");
                        filesFailed++;
                    }
                }
                
                var vpkSignaturesOld = Path.Combine(cs2Path, "game", "csgo", "vpk.signatures.old");
                var vpkSignatures = Path.Combine(cs2Path, "game", "csgo", "vpk.signatures");
                
                if (File.Exists(vpkSignaturesOld))
                {
                    try
                    {
                        if (File.Exists(vpkSignatures))
                        {
                            File.Delete(vpkSignatures);
                        }
                        
                        File.Move(vpkSignaturesOld, vpkSignatures);
                        Log("✓ Restored vpk.signatures from backup");
                        filesRestored++;
                    }
                    catch (Exception ex)
                    {
                        Log($"✗ Failed to restore vpk.signatures: {ex.Message}");
                        filesFailed++;
                    }
                }
                
                Log($"");
                Log($"Verification complete:");
                Log($"  ✓ {filesRestored} files restored");
                if (filesFailed > 0)
                {
                    Log($"  ✗ {filesFailed} files failed");
                }
                Log("");
                Log("Game files have been restored to their original state.");
            }
            catch (Exception ex)
            {
                Log($"Error restoring gameinfo files: {ex.Message}");
                throw;
            }
        }
    }
}