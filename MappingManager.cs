using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Net;
using System.Net.Http;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using System.Threading.Tasks;
using Microsoft.Win32;

namespace CS2KZMappingTools
{
    public class MappingManager
    {
        private static readonly HttpClient httpClient = new HttpClient();
        private const string STEAM_REGISTRY_KEY = @"Software\Valve\Steam";
        private const string METAMOD_LATEST_URL = "https://mms.alliedmods.net/mmsdrop/2.0/mmsource-latest-windows";
        private const string CS2KZ_API_URL = "https://api.github.com/repos/KZGlobalTeam/cs2kz-metamod/releases/latest";
        private const string MAPPING_API_URL = "https://raw.githubusercontent.com/KZGlobalTeam/cs2kz-metamod/refs/heads/master/mapping_api/game/csgo_core/csgo_internal.fgd";
        private const string GAMETRACKING_BASE_URL = "https://raw.githubusercontent.com/SteamDatabase/GameTracking-CS2/refs/heads/master/";

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
                        else
                        {
                            Log($"  Folder entry is not a dictionary");
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

            // Try both casings for steamapps folder
            var libraryFoldersPath = Path.Combine(steamPath, "steamapps", "libraryfolders.vdf");
            if (!File.Exists(libraryFoldersPath))
            {
                libraryFoldersPath = Path.Combine(steamPath, "SteamApps", "libraryfolders.vdf");
            }
            
            var libraryPath = await FindCS2LibraryPathAsync(libraryFoldersPath);
            if (libraryPath == null) 
            {
                Log("Failed to find CS2 library path");
                return null;
            }
            Log($"CS2 library path: {libraryPath}");

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
                    Log($"CS2 manifest file not found at: {manifestPath}");
                    Log($"Tried both 'steamapps' and 'SteamApps' folder names");
                    return null;
                }
                
                var content = await File.ReadAllTextAsync(manifestPath, Encoding.UTF8);
                Log($"Manifest file content preview: {content.Substring(0, Math.Min(200, content.Length))}...");
                
                var parser = new VdfParser();
                var manifestData = parser.Parse(content);
                
                Log($"Manifest root keys: {string.Join(", ", manifestData.Keys)}");

                string? installDir = null;

                // First try AppState structure (older format)
                if (manifestData.TryGetValue("AppState", out var appState) &&
                    appState is Dictionary<string, object> appStateDict)
                {
                    Log($"Found AppState structure, keys: {string.Join(", ", appStateDict.Keys)}");
                    
                    if (appStateDict.TryGetValue("installdir", out var installDirObj))
                    {
                        installDir = installDirObj?.ToString();
                        Log($"Found installdir in AppState: {installDir}");
                    }
                }
                
                // If not found in AppState, try root level (newer format)
                if (installDir == null && manifestData.TryGetValue("installdir", out var rootInstallDirObj))
                {
                    installDir = rootInstallDirObj?.ToString();
                    Log($"Found installdir at root level: {installDir}");
                }

                if (!string.IsNullOrEmpty(installDir))
                {
                    // Try both casings for steamapps folder
                    var cs2Path = Path.Combine(libraryPath, "steamapps", "common", installDir);
                    if (!Directory.Exists(cs2Path))
                    {
                        cs2Path = Path.Combine(libraryPath, "SteamApps", "common", installDir);
                    }
                    
                    Log($"Found CS2 installation at: {cs2Path}");
                    
                    // Verify the path exists
                    if (Directory.Exists(cs2Path))
                    {
                        Log($"CS2 installation path verified: {cs2Path}");
                        return cs2Path;
                    }
                    else
                    {
                        Log($"CS2 installation path does not exist: {cs2Path}");
                    }
                }
                else
                {
                    Log("installdir not found in AppState or root level, showing all available keys...");
                    foreach (var key in manifestData.Keys)
                    {
                        Log($"  Root[{key}] = {manifestData[key]}");
                        if (key.ToLower().Contains("install") || key.ToLower().Contains("dir"))
                        {
                            Log($"    ^^ Potential install directory field: {key} = {manifestData[key]}");
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                Log($"Error reading CS2 manifest: {ex.Message}");
            }

            return null;
        }

        public async Task ModifyGameInfoAsync(string gameInfoPath, string coreGameInfoPath)
        {
            try
            {
                // Modify main gameinfo.gi
                var lines = await File.ReadAllLinesAsync(gameInfoPath);
                var modifiedLines = new List<string>();

                const string targetLine = "			Game	csgo";
                const string newLine = "			Game	csgo/addons/metamod";

                bool metamodAlreadyAdded = lines.Any(l => l.Contains("csgo/addons/metamod"));

                foreach (var line in lines)
                {
                    if (line.Trim() == targetLine.Trim())
                    {
                        // Only add metamod line if not already present
                        if (!metamodAlreadyAdded)
                        {
                            modifiedLines.Add(newLine);
                        }
                        modifiedLines.Add(line);
                    }
                    else
                    {
                        modifiedLines.Add(line);
                    }
                }

                await File.WriteAllLinesAsync(gameInfoPath, modifiedLines);

                // Modify core gameinfo.gi
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
                Log("GameInfo files modified successfully.");
            }
            catch (Exception ex)
            {
                Log($"Error modifying gameinfo files: {ex.Message}");
                throw;
            }
        }

        public Task<(string gameInfo, string backup, string coreGameInfo, string coreBackup)> BackupFilesAsync(string cs2Path)
        {
            var gameInfoPath = Path.Combine(cs2Path, "game", "csgo", "gameinfo.gi");
            var backupPath = Path.Combine(cs2Path, "game", "csgo", "gameinfo.gi.bak");
            var coreGameInfoPath = Path.Combine(cs2Path, "game", "csgo_core", "gameinfo.gi");
            var coreBackupPath = Path.Combine(cs2Path, "game", "csgo_core", "gameinfo.gi.bak");

            try
            {
                if (!File.Exists(gameInfoPath))
                {
                    throw new FileNotFoundException($"GameInfo file not found: {gameInfoPath}");
                }
                if (!File.Exists(coreGameInfoPath))
                {
                    throw new FileNotFoundException($"Core GameInfo file not found: {coreGameInfoPath}");
                }
                
                File.Copy(gameInfoPath, backupPath, true);
                File.Copy(coreGameInfoPath, coreBackupPath, true);
                Log("Files backed up successfully.");
            }
            catch (Exception ex)
            {
                Log($"Error backing up files: {ex.Message}");
                throw;
            }

            return Task.FromResult((gameInfoPath, backupPath, coreGameInfoPath, coreBackupPath));
        }

        public Task RestoreFilesAsync(string backupPath, string gameInfoPath, string coreBackupPath, string coreGameInfoPath)
        {
            try
            {
                if (File.Exists(backupPath))
                {
                    File.Move(backupPath, gameInfoPath, true);
                }
                if (File.Exists(coreBackupPath))
                {
                    File.Move(coreBackupPath, coreGameInfoPath, true);
                }
                Log("Files restored successfully.");
            }
            catch (Exception ex)
            {
                Log($"Error restoring files: {ex.Message}");
            }
            
            return Task.CompletedTask;
        }

        public async Task EnableParticleEditorAsync(string cs2Path)
        {
            Log("Enabling particle editor...");

            var sdkEngineToolsPath = Path.Combine(cs2Path, "game", "bin", "sdkenginetools.txt");
            var assetTypesPath = Path.Combine(cs2Path, "game", "bin", "assettypes_common.txt");

            await ModifyParticleEditorFile(sdkEngineToolsPath, @"(\{[^}]*m_Name = ""pet""[^}]*?)(m_ExcludeFromMods\s*=\s*\[[^\]]*\])");
            await ModifyParticleEditorFile(assetTypesPath, @"(particle_asset\s*=[^}]*?)(m_HideForRetailMods\s*=\s*\[[^\]]*\])");

            Log("Particle editor enabled!");
        }

        private async Task ModifyParticleEditorFile(string filePath, string pattern)
        {
            try
            {
                var content = await File.ReadAllTextAsync(filePath, Encoding.UTF8);
                
                var regex = new Regex(pattern, RegexOptions.Singleline);
                content = regex.Replace(content, match =>
                {
                    var before = match.Groups[1].Value;
                    var excludeSection = match.Groups[2].Value;
                    var commented = string.Join("\n", excludeSection.Split('\n')
                        .Select(line => string.IsNullOrWhiteSpace(line) ? line : "//" + line));
                    return before + commented;
                });

                await File.WriteAllTextAsync(filePath, content, Encoding.UTF8);
                Log($"✓ Modified {Path.GetFileName(filePath)}");
            }
            catch (Exception ex)
            {
                Log($"✗ Error modifying {Path.GetFileName(filePath)}: {ex.Message}");
            }
        }

        public async Task RestoreParticleEditorFilesAsync(string cs2Path)
        {
            Log("Restoring particle editor files...");

            var filePaths = new[]
            {
                "game/bin/sdkenginetools.txt",
                "game/bin/assettypes_common.txt"
            };

            foreach (var filePath in filePaths)
            {
                await DownloadAndSaveFileAsync(GAMETRACKING_BASE_URL + filePath, Path.Combine(cs2Path, filePath));
            }

            Log("Particle editor files restored!");
        }

        public async Task<string?> GetLatestMetamodVersionAsync()
        {
            try
            {
                var response = await httpClient.GetStringAsync(METAMOD_LATEST_URL);
                return response.Trim();
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
                var latestVersion = await GetLatestMetamodVersionAsync();
                if (string.IsNullOrEmpty(latestVersion))
                {
                    throw new Exception("Could not get latest Metamod version");
                }

                var downloadUrl = $"https://mms.alliedmods.net/mmsdrop/2.0/{latestVersion}";
                var tempPath = Path.Combine(Path.GetTempPath(), latestVersion);

                Log($"Downloading Metamod from {downloadUrl}...");
                ProgressIndeterminate?.Invoke();
                var data = await httpClient.GetByteArrayAsync(downloadUrl);
                await File.WriteAllBytesAsync(tempPath, data);
                ProgressUpdated?.Invoke(1, 1);
                Log("Download complete.");

                var outputDir = Path.Combine(cs2Dir, "game", "csgo");
                Log($"Extracting {tempPath} to {outputDir}...");
                
                ZipFile.ExtractToDirectory(tempPath, outputDir, true);
                File.Delete(tempPath);

                Log($"Metamod has been successfully extracted to {outputDir}.");
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
                var response = await httpClient.GetStringAsync(CS2KZ_API_URL);
                var json = JsonDocument.Parse(response);
                return json.RootElement.GetProperty("tag_name").GetString();
            }
            catch (Exception ex)
            {
                Log($"Error getting latest CS2KZ version: {ex.Message}");
                return null;
            }
        }

        public async Task<string?> GetMappingApiHashAsync()
        {
            try
            {
                var data = await httpClient.GetByteArrayAsync(MAPPING_API_URL);
                using var md5 = MD5.Create();
                var hash = md5.ComputeHash(data);
                return Convert.ToHexString(hash).ToLowerInvariant();
            }
            catch (Exception ex)
            {
                Log($"Error getting mapping API hash: {ex.Message}");
                return null;
            }
        }

        public async Task UpdateCS2KZTimeLimitAsync(string cs2Dir)
        {
            var configPath = Path.Combine(cs2Dir, "game", "csgo", "cfg", "cs2kz-server-config.txt");

            if (!File.Exists(configPath))
            {
                Log($"Warning: CS2KZ config not found at {configPath}");
                return;
            }

            try
            {
                var content = await File.ReadAllTextAsync(configPath, Encoding.UTF8);
                var pattern = @"(""defaultTimeLimit""\s+)""60\.0""";
                var replacement = @"${1}""1440.0""";
                var newContent = Regex.Replace(content, pattern, replacement);

                if (newContent != content)
                {
                    await File.WriteAllTextAsync(configPath, newContent, Encoding.UTF8);
                    Log("✓ Updated defaultTimeLimit to 1440.0 (24 hours) in cs2kz-server-config.txt");
                }
                else
                {
                    Log("✓ defaultTimeLimit already set correctly in cs2kz-server-config.txt");
                }
            }
            catch (Exception ex)
            {
                Log($"Warning: Failed to update CS2KZ time limit: {ex.Message}");
            }
        }

        public async Task DownloadCS2KZAsync(string cs2Dir)
        {
            Log("Downloading CS2KZ plugin...");

            try
            {
                // Add User-Agent header for GitHub API
                using var request = new HttpRequestMessage(HttpMethod.Get, CS2KZ_API_URL);
                request.Headers.Add("User-Agent", "CS2KZ-Mapping-Tools");
                
                var response = await httpClient.SendAsync(request);
                if (!response.IsSuccessStatusCode)
                {
                    Log($"GitHub API returned {response.StatusCode}: {response.ReasonPhrase}");
                    
                    // Try alternative approach - check if rate limited
                    if (response.StatusCode == HttpStatusCode.Forbidden)
                    {
                        Log("403 Forbidden - possibly rate limited. Trying alternative download method...");
                        // Try direct latest release download
                        var directUrl = "https://github.com/KZGlobalTeam/cs2kz-metamod/releases/latest/download/cs2kz-windows-master.zip";
                        await DownloadCS2KZDirectAsync(cs2Dir, directUrl);
                        return;
                    }
                    
                    response.EnsureSuccessStatusCode();
                    return;
                }
                
                var responseContent = await response.Content.ReadAsStringAsync();
                var json = JsonDocument.Parse(responseContent);
                var assets = json.RootElement.GetProperty("assets").EnumerateArray();

                foreach (var asset in assets)
                {
                    var name = asset.GetProperty("name").GetString();
                    if (name == "cs2kz-windows-master.zip")
                    {
                        var downloadUrl = asset.GetProperty("browser_download_url").GetString();
                        var tempPath = Path.Combine(Path.GetTempPath(), name);

                        Log($"Downloading CS2KZ from {downloadUrl}...");
                        ProgressIndeterminate?.Invoke();
                        var data = await httpClient.GetByteArrayAsync(downloadUrl);
                        await File.WriteAllBytesAsync(tempPath, data);
                        ProgressUpdated?.Invoke(1, 1);

                        var extractPath = Path.Combine(cs2Dir, "game", "csgo");
                        ZipFile.ExtractToDirectory(tempPath, extractPath, true);
                        File.Delete(tempPath);

                        Log($"CS2KZ unzipped to '{extractPath}'");

                        // Update defaultTimeLimit after extraction
                        await UpdateCS2KZTimeLimitAsync(cs2Dir);
                        break;
                    }
                }

                // Download mapping API FGD
                Log("Downloading mapping API FGD...");
                var fgdPath = Path.Combine(cs2Dir, "game", "csgo_core");
                Directory.CreateDirectory(fgdPath);
                await DownloadAndSaveFileAsync(MAPPING_API_URL, Path.Combine(fgdPath, "csgo_internal.fgd"));
            }
            catch (Exception ex)
            {
                Log($"Error downloading CS2KZ: {ex.Message}");
                throw;
            }
        }

        private async Task DownloadCS2KZDirectAsync(string cs2Dir, string directUrl)
        {
            Log($"Attempting direct download from: {directUrl}");
            
            try
            {
                using var request = new HttpRequestMessage(HttpMethod.Get, directUrl);
                request.Headers.Add("User-Agent", "CS2KZ-Mapping-Tools");
                
                var response = await httpClient.SendAsync(request);
                response.EnsureSuccessStatusCode();

                var tempPath = Path.GetTempFileName() + ".zip";
                await using var fileStream = new FileStream(tempPath, FileMode.Create, FileAccess.Write);
                await response.Content.CopyToAsync(fileStream);

                Log("Direct download complete, extracting...");

                var extractPath = Path.Combine(cs2Dir, "game", "csgo");
                ZipFile.ExtractToDirectory(tempPath, extractPath, true);
                File.Delete(tempPath);

                Log($"CS2KZ unzipped to '{extractPath}'");

                // Update defaultTimeLimit after extraction
                await UpdateCS2KZTimeLimitAsync(cs2Dir);

                // Download mapping API FGD
                Log("Downloading mapping API FGD...");
                var fgdPath = Path.Combine(cs2Dir, "game", "csgo_core");
                Directory.CreateDirectory(fgdPath);
                await DownloadAndSaveFileAsync(MAPPING_API_URL, Path.Combine(fgdPath, "csgo_internal.fgd"));
            }
            catch (Exception ex)
            {
                Log($"Direct download also failed: {ex.Message}");
                throw;
            }
        }

        public Task SetupAssetBinAsync(string cs2Dir)
        {
            Log("Setting up asset bin...");
            
            try
            {
                var sourcePath = Path.Combine(cs2Dir, "game", "csgo", "readonly_tools_asset_info.bin");
                var destPath = Path.Combine(cs2Dir, "game", "csgo", "addons", "metamod", "readonly_tools_asset_info.bin");
                
                Directory.CreateDirectory(Path.GetDirectoryName(destPath) ?? throw new InvalidOperationException("Invalid destination path"));
                File.Copy(sourcePath, destPath, true);
                Log("Asset bin setup complete.");
            }
            catch (Exception ex)
            {
                Log($"Warning: Failed to setup asset bin: {ex.Message}");
            }
            
            return Task.CompletedTask;
        }

        public Task SetupMetamodContentPathAsync(string cs2Path)
        {
            Log("Creating necessary folder for hammer...");
            var path = Path.Combine(cs2Path, "content", "csgo", "addons", "metamod");
            Directory.CreateDirectory(path);
            return Task.CompletedTask;
        }

        public async Task<Dictionary<string, string>> LoadVersionsAsync()
        {
            var versions = new Dictionary<string, string>();
            var tempDir = Environment.GetEnvironmentVariable("TEMP") ?? Path.GetTempPath();
            var appDir = Path.Combine(tempDir, ".CS2KZ-mapping-tools");
            var versionFile = Path.Combine(appDir, "cs2kz_versions.txt");

            if (File.Exists(versionFile))
            {
                try
                {
                    var lines = await File.ReadAllLinesAsync(versionFile);
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
                    Log($"Error loading versions: {ex.Message}");
                }
            }

            return versions;
        }

        public async Task SaveVersionsAsync(Dictionary<string, string> versions)
        {
            var tempDir = Environment.GetEnvironmentVariable("TEMP") ?? Path.GetTempPath();
            var appDir = Path.Combine(tempDir, ".CS2KZ-mapping-tools");
            Directory.CreateDirectory(appDir);
            var versionFile = Path.Combine(appDir, "cs2kz_versions.txt");

            try
            {
                // Load existing versions first
                var existingVersions = await LoadVersionsAsync();
                
                // Merge with new versions (new takes priority)
                foreach (var kvp in versions)
                {
                    existingVersions[kvp.Key] = kvp.Value;
                }

                // Write all versions back
                var lines = existingVersions.Select(kvp => $"{kvp.Key}={kvp.Value}").ToArray();
                await File.WriteAllLinesAsync(versionFile, lines);
            }
            catch (Exception ex)
            {
                Log($"Error saving versions: {ex.Message}");
            }
        }

        public async Task<bool> CheckSetupNeededAsync(string cs2Dir, bool checkMetamod = true, bool checkCS2KZ = true)
        {
            Log("Checking if setup is needed...");

            var metamodPath = Path.Combine(cs2Dir, "game", "csgo", "addons", "metamod");
            var cs2kzPath = Path.Combine(cs2Dir, "game", "csgo", "addons", "cs2kz");

            if (!Directory.Exists(metamodPath) || !Directory.Exists(cs2kzPath))
            {
                Log("Required directories missing - setup needed.");
                return true;
            }

            var currentVersions = await LoadVersionsAsync();

            // Check if we have latest versions cached (from the centralized update checker)
            var latestMetamod = currentVersions.GetValueOrDefault("metamod_latest");
            var latestCS2KZ = currentVersions.GetValueOrDefault("cs2kz_latest");
            var latestMappingApi = currentVersions.GetValueOrDefault("mapping_api_latest");

            if (checkMetamod && !string.IsNullOrEmpty(latestMetamod))
            {
                if (currentVersions.GetValueOrDefault("metamod") != latestMetamod)
                {
                    Log($"Metamod update available ({currentVersions.GetValueOrDefault("metamod")} -> {latestMetamod}) - setup needed.");
                    return true;
                }
            }

            if (checkCS2KZ)
            {
                if (!string.IsNullOrEmpty(latestCS2KZ) && currentVersions.GetValueOrDefault("cs2kz") != latestCS2KZ)
                {
                    Log($"CS2KZ update available ({currentVersions.GetValueOrDefault("cs2kz")} -> {latestCS2KZ}) - setup needed.");
                    return true;
                }
                
                if (!string.IsNullOrEmpty(latestMappingApi) && currentVersions.GetValueOrDefault("mapping_api") != latestMappingApi)
                {
                    Log("Mapping API update available - setup needed.");
                    return true;
                }
            }

            Log("Setup check passed - files up to date.");
            return false;
        }

        public async Task RunSetupAsync(string cs2Dir, bool updateMetamod = true, bool updateCS2KZ = true)
        {
            Log($"Setting up CS2KZ in {cs2Dir}...");

            try
            {
                if (updateMetamod)
                {
                    await DownloadAndExtractMetamodAsync(cs2Dir);
                }
                else
                {
                    Log("Skipping Metamod update (disabled in settings)");
                }

                if (updateCS2KZ)
                {
                    await DownloadCS2KZAsync(cs2Dir);
                }
                else
                {
                    Log("Skipping CS2KZ update (disabled in settings)");
                }

                // Always update CS2KZ time limit configuration
                await UpdateCS2KZTimeLimitAsync(cs2Dir);

                await SetupAssetBinAsync(cs2Dir);
                await SetupMetamodContentPathAsync(cs2Dir);

                // Save version information
                var versions = new Dictionary<string, string>
                {
                    ["metamod"] = updateMetamod ? (await GetLatestMetamodVersionAsync() ?? "unknown") : 
                                 (await LoadVersionsAsync()).GetValueOrDefault("metamod", "unknown"),
                    ["cs2kz"] = updateCS2KZ ? (await GetLatestCS2KZVersionAsync() ?? "unknown") : 
                               (await LoadVersionsAsync()).GetValueOrDefault("cs2kz", "unknown"),
                    ["mapping_api"] = updateCS2KZ ? (await GetMappingApiHashAsync() ?? "unknown") : 
                                     (await LoadVersionsAsync()).GetValueOrDefault("mapping_api", "unknown")
                };

                await SaveVersionsAsync(versions);
                Log("Setup complete.");
            }
            catch (Exception ex)
            {
                Log($"Error during setup: {ex.Message}");
                throw;
            }
        }

        public async Task RunCS2Async(string cs2ToolsPath)
        {
            try
            {
                Log($"Launching CS2 tools from '{cs2ToolsPath}'...");
                
                // Launch CS2 tools directly (csgocfg.exe for Hammer editor)
                var exePath = Path.Combine(cs2ToolsPath, "csgocfg.exe");
                if (!File.Exists(exePath))
                {
                    throw new Exception($"CS2 tools executable not found at: {exePath}");
                }
                
                var startInfo = new ProcessStartInfo
                {
                    FileName = exePath,
                    Arguments = "-insecure -gpuraytracing",
                    WorkingDirectory = cs2ToolsPath,
                    UseShellExecute = false
                };

                var process = Process.Start(startInfo);
                
                // Wait for CS2 tools to actually start
                Log("Waiting for CS2 to launch...");
                await Task.Run(async () =>
                {
                    // Wait up to 30 seconds for CS2 tools to start (csgocfg)
                    for (int i = 0; i < 30; i++)
                    {
                        var csgocfgProcesses = Process.GetProcessesByName("csgocfg");
                        var cs2Processes = Process.GetProcessesByName("cs2");
                        
                        if (csgocfgProcesses.Length > 0 || cs2Processes.Length > 0)
                        {
                            Log($"CS2 process detected (csgocfg: {csgocfgProcesses.Length}, cs2: {cs2Processes.Length})");
                            break;
                        }
                        await Task.Delay(1000);
                    }
                });
                
                // Now wait for both CS2 processes to exit
                await Task.Run(async () =>
                {
                    while (true)
                    {
                        var csgocfgProcesses = Process.GetProcessesByName("csgocfg");
                        var cs2Processes = Process.GetProcessesByName("cs2");
                        
                        if (csgocfgProcesses.Length == 0 && cs2Processes.Length == 0)
                        {
                            break;
                        }
                        
                        await Task.Delay(1000);
                    }
                });

                // Clean up steam_appid.txt if it exists
                var steamAppIdPath = Path.Combine(Directory.GetCurrentDirectory(), "steam_appid.txt");
                if (File.Exists(steamAppIdPath))
                {
                    File.Delete(steamAppIdPath);
                }

                Log("CS2 has been closed.");
            }
            catch (Exception ex)
            {
                Log($"Error running CS2: {ex.Message}");
                throw;
            }
        }

        public async Task VerifyGameInfoAsync(string cs2Path)
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
                        ProgressIndeterminate?.Invoke();
                        
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
                        ProgressUpdated?.Invoke(filesRestored, filePaths.Length);
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
                
                // Also restore particle editor files
                await RestoreParticleEditorFilesAsync(cs2Path);
            }
            catch (Exception ex)
            {
                Log($"Error restoring gameinfo files: {ex.Message}");
                throw;
            }
        }

        private async Task DownloadAndSaveFileAsync(string url, string outputPath)
        {
            try
            {
                Log($"Downloading {url}...");
                ProgressIndeterminate?.Invoke();
                
                using var response = await httpClient.GetAsync(url);
                response.EnsureSuccessStatusCode();
                
                var data = await response.Content.ReadAsByteArrayAsync();
                
                var directory = Path.GetDirectoryName(outputPath);
                if (!string.IsNullOrEmpty(directory))
                {
                    Directory.CreateDirectory(directory);
                }
                
                // Write bytes directly to avoid BOM issues with FGD files
                await File.WriteAllBytesAsync(outputPath, data);
                
                Log($"✓ Downloaded {Path.GetFileName(outputPath)}");
                ProgressUpdated?.Invoke(1, 1); // Complete
            }
            catch (Exception ex)
            {
                Log($"✗ Failed to download {url}: {ex.Message}");
                throw;
            }
        }

        public async Task ExecuteMappingWorkflowAsync(bool updateMetamod = true, bool updateCS2KZ = true)
        {
            try
            {
                var cs2Path = await GetCS2PathAsync();
                if (cs2Path == null)
                {
                    throw new Exception("Failed to get CS2 path. Make sure Steam and CS2 are installed.");
                }

                Log($"CS2 path found: {cs2Path}");

                // Backup files BEFORE setup to ensure they exist
                var gameInfoPath = Path.Combine(cs2Path, "game", "csgo", "gameinfo.gi");
                var coreGameInfoPath = Path.Combine(cs2Path, "game", "csgo_core", "gameinfo.gi");
                
                // If gameinfo files don't exist, restore them first
                if (!File.Exists(gameInfoPath) || !File.Exists(coreGameInfoPath))
                {
                    Log("GameInfo files missing, restoring from Steam database before backup...");
                    await VerifyGameInfoAsync(cs2Path);
                }

                var (gameInfo, backup, coreGameInfo, coreBackup) = await BackupFilesAsync(cs2Path);

                if (await CheckSetupNeededAsync(cs2Path, updateMetamod, updateCS2KZ))
                {
                    Log("Setup needed - running installation...");
                    await RunSetupAsync(cs2Path, updateMetamod, updateCS2KZ);
                }
                else
                {
                    Log("Setup check passed - files up to date.");
                }

                await ModifyGameInfoAsync(gameInfo, coreGameInfo);
                await EnableParticleEditorAsync(cs2Path);

                var cs2ToolsPath = Path.Combine(cs2Path, "game", "bin", "win64");
                await RunCS2Async(cs2ToolsPath);

                await RestoreFilesAsync(backup, gameInfo, coreBackup, coreGameInfo);
                await VerifyGameInfoAsync(cs2Path);

                Log("Mapping workflow completed successfully!");
            }
            catch (Exception ex)
            {
                Log($"Error in mapping workflow: {ex.Message}");
                Log($"Stack trace: {ex.StackTrace}");
                throw;
            }
        }
    }

    // Simple VDF parser for reading Valve Data Format files
    public class VdfParser
    {
        public Dictionary<string, object> Parse(string content)
        {
            var result = new Dictionary<string, object>();
            var lines = content.Split('\n', StringSplitOptions.RemoveEmptyEntries);
            var stack = new Stack<Dictionary<string, object>>();
            stack.Push(result);
            
            for (int i = 0; i < lines.Length; i++)
            {
                var line = lines[i];
                var trimmed = line.Trim();
                
                // Skip empty lines and comments
                if (string.IsNullOrEmpty(trimmed) || trimmed.StartsWith("//"))
                    continue;

                if (trimmed == "{")
                    continue;

                if (trimmed == "}")
                {
                    if (stack.Count > 1)
                        stack.Pop();
                    continue;
                }

                // Handle key-value pairs
                var keyValue = ParseKeyValue(trimmed);
                if (keyValue.HasValue)
                {
                    var (key, value) = keyValue.Value;
                    var current = stack.Peek();
                    
                    // Check if next non-empty line is '{'
                    if (IsNextLineOpenBrace(lines, i))
                    {
                        var subDict = new Dictionary<string, object>();
                        current[key] = subDict;
                        stack.Push(subDict);
                    }
                    else
                    {
                        current[key] = value;
                    }
                }
            }

            return result;
        }
        
        private (string key, string value)? ParseKeyValue(string line)
        {
            // Remove surrounding quotes if present
            line = line.Trim();
            
            // Try to find quoted strings first
            var quotedPattern = @"^""([^""]+)""\s+""([^""]+)""";
            var quotedMatch = System.Text.RegularExpressions.Regex.Match(line, quotedPattern);
            if (quotedMatch.Success)
            {
                return (quotedMatch.Groups[1].Value, quotedMatch.Groups[2].Value);
            }
            
            // Try mixed format (quoted key, unquoted value)
            var mixedPattern = @"^""([^""]+)""\s+([^\s]+)";
            var mixedMatch = System.Text.RegularExpressions.Regex.Match(line, mixedPattern);
            if (mixedMatch.Success)
            {
                return (mixedMatch.Groups[1].Value, mixedMatch.Groups[2].Value.Trim('"'));
            }
            
            // Try tab delimiter
            var parts = line.Split('\t', 2, StringSplitOptions.RemoveEmptyEntries);
            if (parts.Length >= 2)
            {
                var key = parts[0].Trim('"');
                var value = parts[1].Trim('"');
                return (key, value);
            }
            
            // Try multiple spaces/whitespace
            parts = line.Split(new[] { ' ', '\t' }, 2, StringSplitOptions.RemoveEmptyEntries);
            if (parts.Length >= 2)
            {
                var key = parts[0].Trim('"');
                var value = parts[1].Trim('"');
                return (key, value);
            }
            
            return null;
        }

        private bool IsNextLineOpenBrace(string[] lines, int currentIndex)
        {
            for (int i = currentIndex + 1; i < lines.Length; i++)
            {
                var trimmed = lines[i].Trim();
                if (string.IsNullOrEmpty(trimmed) || trimmed.StartsWith("//"))
                    continue;
                return trimmed == "{";
            }
            return false;
        }
    }
}