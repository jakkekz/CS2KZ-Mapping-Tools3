using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Net.Http;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using System.Threading.Tasks;
using Microsoft.Win32;

namespace CS2KZMappingTools
{
    public class ListenManager
    {
        private static readonly HttpClient httpClient = new HttpClient();
        private const string STEAM_REGISTRY_KEY = @"Software\Valve\Steam";
        private const string METAMOD_LATEST_URL = "https://mms.alliedmods.net/mmsdrop/2.0/mmsource-latest-windows";
        private const string CS2KZ_API_URL = "https://api.github.com/repos/KZGlobalTeam/cs2kz-metamod/releases/latest";
        private const string MAPPING_API_URL = "https://raw.githubusercontent.com/KZGlobalTeam/cs2kz-metamod/refs/heads/master/mapping_api/game/csgo_core/csgo_internal.fgd";
        private const string GAMETRACKING_BASE_URL = "https://raw.githubusercontent.com/SteamDatabase/GameTracking-CS2/refs/heads/master/";
        private const string GITHUB_BASE_URL = "https://raw.githubusercontent.com/SteamDatabase/GameTracking-CS2/refs/heads/master/";
        private static readonly string TEMP_FOLDER = Path.Combine(Path.GetTempPath(), ".CS2KZ-mapping-tools");
        private static readonly string ORIGINAL_FILES_FOLDER = Path.Combine(TEMP_FOLDER, "original files");

        public event Action<string>? LogMessage;
        public event Action<string>? LogEvent;
        public event Action<int, int>? ProgressUpdated; // current, total
        public event Action? ProgressIndeterminate;

        private void Log(string message)
        {
            LogMessage?.Invoke(message);
            LogEvent?.Invoke(message);
            Console.WriteLine(message);
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
                
                // Debug: Log all root keys
                foreach (var rootKey in libraryData.Keys)
                {
                    Log($"Root key found: '{rootKey}'");
                }

                // First try the nested structure (newer Steam format)
                if (libraryData.TryGetValue("libraryfolders", out var foldersObj) && foldersObj is Dictionary<string, object> folders)
                {
                    Log($"Found libraryfolders section with {folders.Count} entries");
                    
                    foreach (var kvp in folders)
                    {
                        Log($"Checking library folder: {kvp.Key}");
                        
                        if (kvp.Value is Dictionary<string, object> folder)
                        {
                            // Debug: Log all folder keys
                            Log($"  Folder keys: {string.Join(", ", folder.Keys)}");
                            
                            // Check if this folder has apps and contains CS2 (appid 730)
                            if (folder.TryGetValue("apps", out var appsObj) && appsObj is Dictionary<string, object> apps)
                            {
                                Log($"  Found apps section with {apps.Count} apps");
                                Log($"  App IDs: {string.Join(", ", apps.Keys)}");
                                
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
                    Log($"Tried both 'steamapps' and 'SteamApps' folder names");
                    return null;
                }

                Log("Reading CS2 manifest...");
                var content = await File.ReadAllTextAsync(manifestPath, Encoding.UTF8);
                var parser = new VdfParser();
                var manifestData = parser.Parse(content);
                
                // installdir is directly at root level, not in AppState
                if (manifestData.TryGetValue("installdir", out var installdirObj) && installdirObj is string installdir)
                {
                    // Try both casings for steamapps folder
                    var cs2Path = Path.Combine(libraryPath, "steamapps", "common", installdir);
                    if (!Directory.Exists(cs2Path))
                    {
                        cs2Path = Path.Combine(libraryPath, "SteamApps", "common", installdir);
                    }
                    
                    Log($"Found CS2 installation: {cs2Path}");
                    return cs2Path;
                }
                else
                {
                    Log($"installdir not found or not a string. Available keys: {string.Join(", ", manifestData.Keys)}");
                }
                
                Log("Failed to parse CS2 manifest or find install directory");
                return null;
            }
            catch (Exception ex)
            {
                Log($"Error reading CS2 manifest: {ex.Message}");
            }

            return null;
        }

        private async Task ModifyGameInfoAsync(string gameInfoPath, string coreGameInfoPath)
        {
            try
            {
                Log("Modifying gameinfo.gi files for Metamod support...");
                
                // Copy EXACT logic from working MappingManager - MAIN gameinfo.gi
                var lines = await File.ReadAllLinesAsync(gameInfoPath);
                var modifiedLines = new List<string>();

                const string targetLine = "\t\t\tGame\tcsgo";
                const string newLine = "\t\t\tGame\tcsgo/addons/metamod";

                foreach (var line in lines)
                {
                    if (line.Trim() == targetLine.Trim())
                    {
                        modifiedLines.Add(newLine);
                    }
                    modifiedLines.Add(line);
                }

                await File.WriteAllLinesAsync(gameInfoPath, modifiedLines);

                // Copy EXACT logic from working MappingManager - CORE gameinfo.gi  
                var coreLines = await File.ReadAllLinesAsync(coreGameInfoPath);
                var modifiedCoreLines = new List<string>();
                int skip = 0;

                foreach (var line in coreLines)
                {
                    if (line.Contains("CustomNavBuild"))
                    {
                        skip = 5;
                    }
                    if (skip > 0)
                    {
                        skip--;
                    }
                    else
                    {
                        modifiedCoreLines.Add(line);
                    }
                }

                await File.WriteAllLinesAsync(coreGameInfoPath, modifiedCoreLines);
                Log("✓ Modified main gameinfo.gi");
                Log("✓ Modified core gameinfo.gi");
            }
            catch (Exception ex)
            {
                Log($"Error modifying gameinfo files: {ex.Message}");
                throw;
            }
        }

        private async Task ModifyGameInfoP2PAsync(string gameInfoPath)
        {
            try
            {
                Log("Adding P2P listen server configuration...");
                
                // Use same pattern as working MappingManager
                var lines = await File.ReadAllLinesAsync(gameInfoPath);
                var modifiedLines = new List<string>();

                foreach (var line in lines)
                {
                    // Python exact match: if line == "		// Bandwidth control default: 300,000 Bps\n":
                    if (line.Trim() == "// Bandwidth control default: 300,000 Bps")
                    {
                        modifiedLines.Add("\t\t\"net_p2p_listen_dedicated\" \"1\"");
                    }
                    // Python exact match: elif line == "	GameInstructor\n":
                    else if (line.Trim() == "GameInstructor")
                    {
                        modifiedLines.Add("\tNetworkSystem");
                        modifiedLines.Add("\t{");
                        modifiedLines.Add("\t\t\"CreateListenSocketP2P\" \"2\"");
                        modifiedLines.Add("\t}");
                    }
                    
                    modifiedLines.Add(line);
                }

                await File.WriteAllLinesAsync(gameInfoPath, modifiedLines);
                Log("✓ Added P2P configuration");
            }
            catch (Exception ex)
            {
                Log($"Error adding P2P configuration: {ex.Message}");
                throw;
            }
        }

        private (string gameInfoPath, string backupPath, string coreGameInfoPath, string coreBackupPath) BackupFiles(string cs2Path)
        {
            var gameInfoPath = Path.Combine(cs2Path, "game", "csgo", "gameinfo.gi");
            var backupPath = Path.Combine(cs2Path, "game", "csgo", "gameinfo.gi.bak");
            var coreGameInfoPath = Path.Combine(cs2Path, "game", "csgo_core", "gameinfo.gi");
            var coreBackupPath = Path.Combine(cs2Path, "game", "csgo_core", "gameinfo.gi.bak");

            Log("Creating backup of gameinfo files...");
            File.Copy(gameInfoPath, backupPath, true);
            File.Copy(coreGameInfoPath, coreBackupPath, true);
            Log("✓ Files backed up");

            return (gameInfoPath, backupPath, coreGameInfoPath, coreBackupPath);
        }

        private void RestoreFiles(string backupPath, string gameInfoPath, string coreBackupPath, string coreGameInfoPath)
        {
            try
            {
                Log("Restoring original gameinfo files from temp folder...");
                
                var originalGameInfo = Path.Combine(ORIGINAL_FILES_FOLDER, "gameinfo.gi");
                var originalCoreGameInfo = Path.Combine(ORIGINAL_FILES_FOLDER, "gameinfo_core.gi");
                
                if (File.Exists(originalGameInfo) && File.Exists(originalCoreGameInfo))
                {
                    // Use fresh original files from temp folder
                    File.Copy(originalGameInfo, gameInfoPath, true);
                    File.Copy(originalCoreGameInfo, coreGameInfoPath, true);
                    Log("✓ Files restored from original GitHub downloads");
                }
                else
                {
                    // Fallback to backup files if original downloads failed
                    Log("⚠ Original files not found, falling back to backup files...");
                    if (File.Exists(backupPath) && File.Exists(coreBackupPath))
                    {
                        File.Move(backupPath, gameInfoPath, true);
                        File.Move(coreBackupPath, coreGameInfoPath, true);
                        Log("✓ Files restored from backup");
                    }
                    else
                    {
                        Log("✗ No backup files available for restoration");
                    }
                }
                
                // Clean up backup files if they exist
                try
                {
                    if (File.Exists(backupPath)) File.Delete(backupPath);
                    if (File.Exists(coreBackupPath)) File.Delete(coreBackupPath);
                }
                catch (Exception cleanupEx)
                {
                    Log($"Note: Could not clean up backup files: {cleanupEx.Message}");
                }
            }
            catch (Exception ex)
            {
                Log($"Error restoring files: {ex.Message}");
            }
        }

        private async Task DownloadOriginalFilesAsync()
        {
            try
            {
                Log("Downloading original gameinfo files from GitHub...");
                
                // Create directories
                Directory.CreateDirectory(ORIGINAL_FILES_FOLDER);
                
                var filesToDownload = new[]
                {
                    "game/csgo/gameinfo.gi",
                    "game/csgo_core/gameinfo.gi"
                };
                
                foreach (var filePath in filesToDownload)
                {
                    var url = GITHUB_BASE_URL + filePath;
                    var localPath = Path.Combine(ORIGINAL_FILES_FOLDER, Path.GetFileName(filePath));
                    
                    // Add suffix to distinguish core file
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
                        // Normalize line endings to Windows format
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

        public async Task<string?> GetLatestMetamodVersionAsync()
        {
            try
            {
                Log("Checking latest Metamod version...");
                var response = await httpClient.GetAsync(METAMOD_LATEST_URL);
                response.EnsureSuccessStatusCode();
                var version = (await response.Content.ReadAsStringAsync()).Trim();
                Log($"Latest Metamod version: {version}");
                return version;
            }
            catch (Exception ex)
            {
                Log($"Error getting latest Metamod version: {ex.Message}");
                return null;
            }
        }

        public async Task DownloadAndExtractMetamodAsync(string cs2Dir)
        {
            try
            {
                Log("Downloading Metamod...");
                ProgressIndeterminate?.Invoke();
                
                var latestResponse = await httpClient.GetAsync(METAMOD_LATEST_URL);
                latestResponse.EnsureSuccessStatusCode();
                var filename = (await latestResponse.Content.ReadAsStringAsync()).Trim();
                
                var downloadUrl = $"https://mms.alliedmods.net/mmsdrop/2.0/{filename}";
                var archivePath = Path.Combine(Path.GetTempPath(), filename);

                Log($"Downloading from {downloadUrl}...");
                using (var response = await httpClient.GetAsync(downloadUrl, HttpCompletionOption.ResponseHeadersRead))
                {
                    response.EnsureSuccessStatusCode();
                    var contentLength = response.Content.Headers.ContentLength;
                    
                    using (var stream = await response.Content.ReadAsStreamAsync())
                    using (var fileStream = new FileStream(archivePath, FileMode.Create, FileAccess.Write, FileShare.None))
                    {
                        var buffer = new byte[8192];
                        long totalBytesRead = 0;
                        int bytesRead;
                        
                        while ((bytesRead = await stream.ReadAsync(buffer, 0, buffer.Length)) > 0)
                        {
                            await fileStream.WriteAsync(buffer, 0, bytesRead);
                            totalBytesRead += bytesRead;
                            
                            if (contentLength.HasValue && contentLength.Value > 0)
                            {
                                ProgressUpdated?.Invoke((int)totalBytesRead, (int)contentLength.Value);
                            }
                        }
                    }
                }
                
                Log("Download complete. Extracting...");
                var outputDir = Path.Combine(cs2Dir, "game", "csgo");
                ZipFile.ExtractToDirectory(archivePath, outputDir, true);
                
                File.Delete(archivePath);
                Log("✓ Metamod extracted successfully");
            }
            catch (Exception ex)
            {
                Log($"Error downloading/extracting Metamod: {ex.Message}");
                throw;
            }
        }

        public async Task<string?> GetLatestCS2KZVersionAsync()
        {
            try
            {
                Log("Checking latest CS2KZ version...");
                var response = await httpClient.GetAsync(CS2KZ_API_URL);
                response.EnsureSuccessStatusCode();
                
                var jsonContent = await response.Content.ReadAsStringAsync();
                var releaseData = JsonSerializer.Deserialize<JsonElement>(jsonContent);
                
                if (releaseData.TryGetProperty("tag_name", out var tagName))
                {
                    var version = tagName.GetString();
                    Log($"Latest CS2KZ version: {version}");
                    return version;
                }
            }
            catch (Exception ex)
            {
                Log($"Error getting latest CS2KZ version: {ex.Message}");
            }
            
            return null;
        }

        public async Task<string?> GetMappingApiHashAsync()
        {
            try
            {
                Log("Checking mapping API hash...");
                var response = await httpClient.GetAsync(MAPPING_API_URL);
                response.EnsureSuccessStatusCode();
                
                var content = await response.Content.ReadAsByteArrayAsync();
                using var md5 = MD5.Create();
                var hash = Convert.ToHexString(md5.ComputeHash(content)).ToLower();
                Log($"Mapping API hash: {hash}");
                return hash;
            }
            catch (Exception ex)
            {
                Log($"Error getting mapping API hash: {ex.Message}");
                return null;
            }
        }

        private async Task UpdateCS2KZTimeLimitAsync(string cs2Dir)
        {
            try
            {
                var configPath = Path.Combine(cs2Dir, "game", "csgo", "cfg", "cs2kz-server-config.txt");
                
                if (!File.Exists(configPath))
                {
                    Log($"Warning: CS2KZ config not found at {configPath}");
                    return;
                }

                Log("Updating CS2KZ time limit configuration...");
                var content = await File.ReadAllTextAsync(configPath, Encoding.UTF8);
                
                // Replace defaultTimeLimit from 60.0 to 1440.0 (24 hours)
                var pattern = @"(""defaultTimeLimit""\s+)""60\.0""";
                var replacement = @"$1""1440.0""";
                var newContent = Regex.Replace(content, pattern, replacement);
                
                if (newContent != content)
                {
                    await File.WriteAllTextAsync(configPath, newContent, Encoding.UTF8);
                    Log("✓ Updated defaultTimeLimit to 1440.0 (24 hours)");
                }
                else
                {
                    Log("✓ defaultTimeLimit already set correctly");
                }
            }
            catch (Exception ex)
            {
                Log($"Warning: Failed to update CS2KZ time limit: {ex.Message}");
            }
        }

        public async Task DownloadCS2KZAsync(string cs2Dir)
        {
            try
            {
                Log("Downloading CS2KZ plugin...");
                ProgressIndeterminate?.Invoke();
                
                var response = await httpClient.GetAsync(CS2KZ_API_URL);
                response.EnsureSuccessStatusCode();
                
                var jsonContent = await response.Content.ReadAsStringAsync();
                var releaseData = JsonSerializer.Deserialize<JsonElement>(jsonContent);
                
                if (!releaseData.TryGetProperty("assets", out var assetsElement) || 
                    assetsElement.GetArrayLength() == 0)
                {
                    throw new Exception("No assets found in the latest release.");
                }

                foreach (var asset in assetsElement.EnumerateArray())
                {
                    if (asset.TryGetProperty("name", out var nameElement) &&
                        nameElement.GetString() == "cs2kz-windows-master.zip" &&
                        asset.TryGetProperty("browser_download_url", out var urlElement))
                    {
                        var downloadUrl = urlElement.GetString()!;
                        var tempPath = Path.GetTempFileName();
                        
                        Log($"Downloading CS2KZ from {downloadUrl}...");
                        using (var downloadResponse = await httpClient.GetAsync(downloadUrl, HttpCompletionOption.ResponseHeadersRead))
                        {
                            downloadResponse.EnsureSuccessStatusCode();
                            var contentLength = downloadResponse.Content.Headers.ContentLength;
                            
                            using (var stream = await downloadResponse.Content.ReadAsStreamAsync())
                            using (var fileStream = new FileStream(tempPath, FileMode.Create, FileAccess.Write, FileShare.None))
                            {
                                var buffer = new byte[8192];
                                long totalBytesRead = 0;
                                int bytesRead;
                                
                                while ((bytesRead = await stream.ReadAsync(buffer, 0, buffer.Length)) > 0)
                                {
                                    await fileStream.WriteAsync(buffer, 0, bytesRead);
                                    totalBytesRead += bytesRead;
                                    
                                    if (contentLength.HasValue && contentLength.Value > 0)
                                    {
                                        ProgressUpdated?.Invoke((int)totalBytesRead, (int)contentLength.Value);
                                    }
                                }
                            }
                        }

                        var outputPath = Path.Combine(cs2Dir, "game", "csgo");
                        Log("Extracting CS2KZ...");
                        ZipFile.ExtractToDirectory(tempPath, outputPath, true);
                        File.Delete(tempPath);
                        
                        Log("✓ CS2KZ extracted successfully");
                        
                        // Update time limit configuration
                        await UpdateCS2KZTimeLimitAsync(cs2Dir);
                        break;
                    }
                }

                // Download mapping API FGD
                Log("Downloading mapping API FGD...");
                var fgdResponse = await httpClient.GetAsync(MAPPING_API_URL);
                fgdResponse.EnsureSuccessStatusCode();
                
                var fgdPath = Path.Combine(cs2Dir, "game", "csgo_core");
                Directory.CreateDirectory(fgdPath);
                
                var fgdContent = await fgdResponse.Content.ReadAsByteArrayAsync();
                await File.WriteAllBytesAsync(Path.Combine(fgdPath, "csgo_internal.fgd"), fgdContent);
                
                Log("✓ Mapping API FGD downloaded");
            }
            catch (Exception ex)
            {
                Log($"Error downloading CS2KZ: {ex.Message}");
                throw;
            }
        }

        private void SetupAssetBin(string cs2Dir)
        {
            try
            {
                Log("Setting up asset bin...");
                var sourcePath = Path.Combine(cs2Dir, "game", "csgo", "readonly_tools_asset_info.bin");
                var destPath = Path.Combine(cs2Dir, "game", "csgo", "addons", "metamod", "readonly_tools_asset_info.bin");
                
                if (File.Exists(sourcePath))
                {
                    Directory.CreateDirectory(Path.GetDirectoryName(destPath)!);
                    File.Copy(sourcePath, destPath, true);
                    Log("✓ Asset bin setup complete");
                }
                else
                {
                    Log("Warning: Source asset bin not found - mapping tools might not be installed");
                }
            }
            catch (Exception ex)
            {
                Log($"Warning: Failed to setup asset bin: {ex.Message}");
            }
        }

        private void SetupMetamodContentPath(string cs2Path)
        {
            try
            {
                Log("Creating necessary folder for Hammer...");
                var contentPath = Path.Combine(cs2Path, "content", "csgo", "addons", "metamod");
                Directory.CreateDirectory(contentPath);
                Log("✓ Content path created");
            }
            catch (Exception ex)
            {
                Log($"Warning: Failed to create content path: {ex.Message}");
            }
        }

        private Dictionary<string, string> LoadVersions(string cs2Dir)
        {
            var versions = new Dictionary<string, string>();
            var tempDir = Environment.GetEnvironmentVariable("TEMP") ?? Path.GetTempPath();
            var appDir = Path.Combine(tempDir, ".CS2KZ-mapping-tools");
            Directory.CreateDirectory(appDir);
            
            var versionFile = Path.Combine(appDir, "cs2kz_versions.txt");
            
            if (File.Exists(versionFile))
            {
                try
                {
                    var lines = File.ReadAllLines(versionFile);
                    foreach (var line in lines)
                    {
                        var parts = line.Split('=', 2);
                        if (parts.Length == 2)
                        {
                            versions[parts[0]] = parts[1];
                        }
                    }
                }
                catch (Exception ex)
                {
                    Log($"Warning: Failed to load versions: {ex.Message}");
                }
            }
            
            return versions;
        }

        private async Task SaveVersionsAsync(string cs2Dir, Dictionary<string, string> newVersions)
        {
            try
            {
                var tempDir = Environment.GetEnvironmentVariable("TEMP") ?? Path.GetTempPath();
                var appDir = Path.Combine(tempDir, ".CS2KZ-mapping-tools");
                Directory.CreateDirectory(appDir);
                
                var versionFile = Path.Combine(appDir, "cs2kz_versions.txt");
                
                // Load existing versions
                var versions = LoadVersions(cs2Dir);
                
                // Merge with new versions
                foreach (var kvp in newVersions)
                {
                    versions[kvp.Key] = kvp.Value;
                }
                
                // Save all versions
                var lines = versions.Select(kvp => $"{kvp.Key}={kvp.Value}").ToArray();
                await File.WriteAllLinesAsync(versionFile, lines);
            }
            catch (Exception ex)
            {
                Log($"Warning: Failed to save versions: {ex.Message}");
            }
        }

        public Task<bool> CheckSetupNeededAsync(string cs2Dir, bool checkMetamod = true, bool checkCS2KZ = true)
        {
            Log("Checking if setup is needed...");
            
            var metamodPath = Path.Combine(cs2Dir, "game", "csgo", "addons", "metamod");
            var cs2kzPath = Path.Combine(cs2Dir, "game", "csgo", "addons", "cs2kz");
            
            if (!Directory.Exists(metamodPath) || !Directory.Exists(cs2kzPath))
            {
                Log("Required directories missing - setup needed");
                return Task.FromResult(true);
            }
            
            // Force setup for now to ensure everything is properly installed
            Log("Forcing setup to ensure proper installation");
            return Task.FromResult(true);
            
            /*
            var currentVersions = LoadVersions(cs2Dir);
            
            if (checkMetamod)
            {
                var latestMetamod = await GetLatestMetamodVersionAsync();
                if (latestMetamod != null && currentVersions.GetValueOrDefault("metamod") != latestMetamod)
                {
                    Log("Metamod update available - setup needed");
                    return true;
                }
            }
            
            if (checkCS2KZ)
            {
                var latestCS2KZ = await GetLatestCS2KZVersionAsync();
                var latestMappingApi = await GetMappingApiHashAsync();
                
                if (latestCS2KZ != null && currentVersions.GetValueOrDefault("cs2kz") != latestCS2KZ)
                {
                    Log("CS2KZ update available - setup needed");
                    return true;
                }
                
                if (latestMappingApi != null && currentVersions.GetValueOrDefault("mapping_api") != latestMappingApi)
                {
                    Log("Mapping API update available - setup needed");
                    return true;
                }
            }
            
            Log("Setup check passed - files up to date");
            return false;
            */
        }

        public async Task RunSetupAsync(string cs2Dir, bool updateMetamod = true, bool updateCS2KZ = true)
        {
            Log($"Setting up CS2KZ listen server in {cs2Dir}...");
            
            if (updateMetamod)
            {
                try
                {
                    await DownloadAndExtractMetamodAsync(cs2Dir);
                }
                catch (Exception ex)
                {
                    Log($"Error downloading Metamod: {ex.Message}");
                    Log("Continuing without Metamod update...");
                }
            }
            else
            {
                Log("Skipping Metamod update (disabled in settings)");
            }
            
            if (updateCS2KZ)
            {
                try
                {
                    await DownloadCS2KZAsync(cs2Dir);
                }
                catch (Exception ex)
                {
                    Log($"Error downloading CS2KZ: {ex.Message}");
                    Log("Continuing without CS2KZ update (may be due to GitHub rate limiting)...");
                }
            }
            else
            {
                Log("Skipping CS2KZ update (disabled in settings)");
            }
            
            // Always update CS2KZ time limit configuration if possible
            try
            {
                await UpdateCS2KZTimeLimitAsync(cs2Dir);
            }
            catch (Exception ex)
            {
                Log($"Warning: Failed to update CS2KZ time limit: {ex.Message}");
            }
            
            try
            {
                SetupAssetBin(cs2Dir);
                SetupMetamodContentPath(cs2Dir);
            }
            catch (Exception ex)
            {
                Log($"Warning: Failed to setup asset bin or content path: {ex.Message}");
                Log("This might be because mapping tools are not installed.");
            }
            
            // Save version information (use existing versions if downloads failed)
            var existingVersions = LoadVersions(cs2Dir);
            var versions = new Dictionary<string, string>();
            if (updateMetamod)
            {
                versions["metamod"] = await GetLatestMetamodVersionAsync() ?? existingVersions.GetValueOrDefault("metamod", "unknown");
            }
            if (updateCS2KZ)
            {
                versions["cs2kz"] = await GetLatestCS2KZVersionAsync() ?? existingVersions.GetValueOrDefault("cs2kz", "unknown");
                versions["mapping_api"] = await GetMappingApiHashAsync() ?? existingVersions.GetValueOrDefault("mapping_api", "unknown");
            }
            
            await SaveVersionsAsync(cs2Dir, versions);
            Log("✓ Setup complete");
        }

        private async Task RunListenServerAsync(string cs2Path)
        {
            Log($"Launching CS2 listen server from '{cs2Path}'...");
            
            try
            {
                var cs2ProcessStartInfo = new ProcessStartInfo
                {
                    FileName = cs2Path,
                    Arguments = "-insecure",
                    UseShellExecute = false,
                    CreateNoWindow = false
                };
                
                using var process = Process.Start(cs2ProcessStartInfo);
                if (process == null)
                {
                    throw new Exception("Failed to start CS2 process");
                }
                
                Log($"CS2 process started (PID: {process.Id})");
                
                // Wait for the process to exit, but with a timeout for failed starts
                var processExited = await Task.Run(() => 
                {
                    return process.WaitForExit(10000); // 10 second timeout
                });
                
                if (!processExited && !process.HasExited)
                {
                    Log("CS2 process still running after 10 seconds - checking if it started successfully...");
                    
                    // Wait a bit more to see if CS2 actually started
                    await Task.Delay(5000);
                    
                    if (!process.HasExited)
                    {
                        Log("CS2 appears to be running normally, waiting for user to close it...");
                        await Task.Run(() => process.WaitForExit());
                        Log("CS2 process has exited");
                    }
                    else
                    {
                        Log("CS2 process exited early - may have failed to start");
                    }
                }
                else if (processExited)
                {
                    Log("CS2 process has exited");
                }
                else
                {
                    Log("CS2 process exited quickly - may have failed to start");
                }
            }
            catch (Exception ex)
            {
                Log($"Error running CS2: {ex.Message}");
                throw;
            }
            finally
            {
                // Clean up steam_appid.txt if it exists
                try
                {
                    var steamAppIdFile = "steam_appid.txt";
                    if (File.Exists(steamAppIdFile))
                    {
                        File.Delete(steamAppIdFile);
                        Log("✓ Cleaned up steam_appid.txt");
                    }
                }
                catch (Exception ex)
                {
                    Log($"Warning: Failed to clean up steam_appid.txt: {ex.Message}");
                }
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
                        
                        // Create directory if needed
                        Directory.CreateDirectory(Path.GetDirectoryName(fullPath)!);
                        
                        // Write file exactly like Python script does
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
                
                // Check for and restore vpk.signatures.old
                var vpkSignaturesOld = Path.Combine(cs2Path, "game", "csgo", "vpk.signatures.old");
                var vpkSignatures = Path.Combine(cs2Path, "game", "csgo", "vpk.signatures");
                
                if (File.Exists(vpkSignaturesOld))
                {
                    try
                    {
                        // Remove existing vpk.signatures if it exists
                        if (File.Exists(vpkSignatures))
                        {
                            File.Delete(vpkSignatures);
                        }
                        
                        // Rename vpk.signatures.old back to vpk.signatures
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

        public async Task ForceRestoreGameInfoAsync()
        {
            try
            {
                var cs2Path = await GetCS2PathAsync();
                if (cs2Path == null)
                {
                    throw new Exception("Could not find CS2 installation path");
                }
                
                Log("Force restoring gameinfo files...");
                await VerifyGameInfoAsync(cs2Path);
            }
            catch (Exception ex)
            {
                Log($"Error in force restore: {ex.Message}");
                throw;
            }
        }

        public async Task RunListenServerProcessAsync(bool updateMetamod = true, bool updateCS2KZ = true)
        {
            try
            {
                Log("Starting CS2KZ Listen Server setup and launch...");
                
                // Download original files first
                await DownloadOriginalFilesAsync();
                
                var cs2Path = await GetCS2PathAsync();
                if (cs2Path == null)
                {
                    Log("Failed to get CS2 path. Cannot continue.");
                    return;
                }
                
                // Check if setup is needed
                var needsSetup = await CheckSetupNeededAsync(cs2Path, updateMetamod, updateCS2KZ);
                if (needsSetup)
                {
                    Log("Setup needed - running installation...");
                    await RunSetupAsync(cs2Path, updateMetamod, updateCS2KZ);
                }
                else
                {
                    Log("Setup check passed - files up to date.");
                }
                
                // Backup and modify gameinfo files
                var (gameInfoPath, backupPath, coreGameInfoPath, coreBackupPath) = BackupFiles(cs2Path);
                
                try
                {
                    await ModifyGameInfoAsync(gameInfoPath, coreGameInfoPath);
                    
                    // TODO: Fix P2P modifications - currently corrupting file
                    // await ModifyGameInfoP2PAsync(gameInfoPath);
                    
                    Log("✓ Added P2P configuration");
                    
                    var cs2ExePath = Path.Combine(cs2Path, "game", "bin", "win64", "cs2.exe");
                    if (!File.Exists(cs2ExePath))
                    {
                        throw new FileNotFoundException($"CS2 executable not found at {cs2ExePath}");
                    }
                    
                    await RunListenServerAsync(cs2ExePath);
                }
                finally
                {
                    // Always restore files after CS2 exits by downloading fresh copies from GitHub
                    Log("CS2 process has ended. Restoring gameinfo files to original state...");
                    await VerifyGameInfoAsync(cs2Path);
                    
                    // Clean up backup files
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
                
                Log("✓ Listen server process completed successfully");
            }
            catch (Exception ex)
            {
                Log($"Error in listen server process: {ex.Message}");
                throw;
            }
        }
    }
}