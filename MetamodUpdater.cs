using System;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Net.Http;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;

namespace CS2KZMappingTools
{
    public class MetamodUpdater
    {
        private const string METAMOD_VERSION_URL = "https://mms.alliedmods.net/mmsdrop/2.0/mmsource-latest-windows";
        private const string CS2KZ_API_URL = "https://api.github.com/repos/KZGlobalTeam/cs2kz-metamod/releases/latest";
        private const string MAPPING_API_URL = "https://raw.githubusercontent.com/KZGlobalTeam/cs2kz-metamod/refs/heads/master/mapping_api/game/csgo_core/csgo_internal.fgd";
        
        private readonly string _versionFile;
        
        public event EventHandler<int>? DownloadProgressChanged;
        public event EventHandler<string>? StatusChanged;
        
        public MetamodUpdater()
        {
            string basePath = Path.Combine(Path.GetTempPath(), ".CS2KZ-mapping-tools");
            Directory.CreateDirectory(basePath);
            _versionFile = Path.Combine(basePath, "cs2kz_versions.txt");
        }
        
        private string? GetCS2Path()
        {
            try
            {
                // Get Steam path from registry
                using var key = Microsoft.Win32.Registry.CurrentUser.OpenSubKey(@"Software\Valve\Steam");
                if (key == null) return null;
                
                string? steamPath = key.GetValue("SteamPath") as string;
                if (string.IsNullOrEmpty(steamPath)) return null;
                
                // Read library folders
                string libraryFoldersPath = Path.Combine(steamPath, "steamapps", "libraryfolders.vdf");
                if (!File.Exists(libraryFoldersPath)) return null;
                
                // Parse VDF file to find CS2 installation
                string content = File.ReadAllText(libraryFoldersPath);
                
                // Simple VDF parsing - look for paths and check for CS2 (appid 730)
                var lines = content.Split('\n');
                string? currentPath = null;
                
                foreach (var line in lines)
                {
                    if (line.Contains("\"path\""))
                    {
                        int start = line.IndexOf("\"path\"") + 7;
                        int valueStart = line.IndexOf('\"', start) + 1;
                        int valueEnd = line.IndexOf('\"', valueStart);
                        if (valueStart > 0 && valueEnd > valueStart)
                        {
                            currentPath = line.Substring(valueStart, valueEnd - valueStart).Replace("\\\\", "\\");
                        }
                    }
                    else if (line.Contains("\"730\"") && currentPath != null)
                    {
                        string cs2Path = Path.Combine(currentPath, "steamapps", "common", "Counter-Strike Global Offensive");
                        if (Directory.Exists(cs2Path))
                        {
                            return cs2Path;
                        }
                    }
                }
                
                return null;
            }
            catch
            {
                return null;
            }
        }
        
        public async Task<UpdateStatus> CheckForUpdatesAsync(bool checkRemote = true)
        {
            var status = new UpdateStatus();
            
            try
            {
                string? cs2Path = GetCS2Path();
                if (cs2Path == null)
                {
                    status.Error = "CS2 installation not found";
                    return status;
                }
                
                // Always load current versions from the tracking file
                var currentVersions = LoadVersions();
                
                // Check if Metamod and CS2KZ are installed based on version tracking file
                // If version is tracked in the file, we consider it installed
                status.MetamodInstalled = currentVersions.ContainsKey("metamod") && !string.IsNullOrEmpty(currentVersions["metamod"]);
                status.CS2KZInstalled = currentVersions.ContainsKey("cs2kz") && !string.IsNullOrEmpty(currentVersions["cs2kz"]);
                
                status.MetamodCurrentVersion = currentVersions.GetValueOrDefault("metamod", "");
                status.CS2KZCurrentVersion = currentVersions.GetValueOrDefault("cs2kz", "");
                status.MappingAPICurrentHash = currentVersions.GetValueOrDefault("mapping_api", "");
                
                // Only check remote versions if requested
                if (!checkRemote)
                {
                    return status;
                }
                
                // Check Metamod version
                using var httpClient = new HttpClient();
                httpClient.Timeout = TimeSpan.FromSeconds(10);
                httpClient.DefaultRequestHeaders.Add("User-Agent", "CS2KZ-Mapping-Tools");
                
                try
                {
                    var metamodResponse = await httpClient.GetStringAsync(METAMOD_VERSION_URL);
                    string latestMetamod = metamodResponse.Trim();
                    status.MetamodLatestVersion = latestMetamod;
                    
                    // Need update if: not installed, no version tracked, or version doesn't match
                    status.MetamodUpdateAvailable = !status.MetamodInstalled || 
                        string.IsNullOrEmpty(status.MetamodCurrentVersion) || 
                        status.MetamodCurrentVersion != latestMetamod;
                }
                catch
                {
                    // If can't check, assume update needed if not installed
                    status.MetamodUpdateAvailable = !status.MetamodInstalled;
                }
                
                // Check CS2KZ version
                try
                {
                    var cs2kzResponse = await httpClient.GetStringAsync(CS2KZ_API_URL);
                    using var doc = JsonDocument.Parse(cs2kzResponse);
                    string latestCS2KZ = doc.RootElement.GetProperty("tag_name").GetString() ?? "";
                    status.CS2KZLatestVersion = latestCS2KZ;
                    
                    // Need update if: not installed, no version tracked, or version doesn't match
                    status.CS2KZUpdateAvailable = !status.CS2KZInstalled || 
                        string.IsNullOrEmpty(status.CS2KZCurrentVersion) || 
                        status.CS2KZCurrentVersion != latestCS2KZ;
                }
                catch
                {
                    // If can't check, assume update needed if not installed
                    status.CS2KZUpdateAvailable = !status.CS2KZInstalled;
                }
                
                // Check Mapping API hash
                try
                {
                    var mappingApiResponse = await httpClient.GetByteArrayAsync(MAPPING_API_URL);
                    string latestHash = ComputeMD5Hash(mappingApiResponse);
                    status.MappingAPILatestHash = latestHash;
                    
                    // Need update if no hash tracked or hash doesn't match
                    status.MappingAPIUpdateAvailable = string.IsNullOrEmpty(status.MappingAPICurrentHash) || 
                        status.MappingAPICurrentHash != latestHash;
                }
                catch
                {
                    status.MappingAPIUpdateAvailable = false;
                }
                
                return status;
            }
            catch (Exception ex)
            {
                status.Error = ex.Message;
                return status;
            }
        }
        
        public async Task<bool> UpdateAllAsync()
        {
            try
            {
                string? cs2Path = GetCS2Path();
                if (cs2Path == null)
                {
                    StatusChanged?.Invoke(this, "CS2 installation not found");
                    return false;
                }
                
                StatusChanged?.Invoke(this, "Checking for updates...");
                var status = await CheckForUpdatesAsync();
                
                bool needsUpdate = status.MetamodUpdateAvailable || 
                                  status.CS2KZUpdateAvailable || 
                                  status.MappingAPIUpdateAvailable ||
                                  !status.MetamodInstalled ||
                                  !status.CS2KZInstalled;
                
                if (!needsUpdate)
                {
                    StatusChanged?.Invoke(this, "All components up to date");
                    return true;
                }
                
                // Update Metamod if needed
                if (!status.MetamodInstalled || status.MetamodUpdateAvailable)
                {
                    await DownloadAndInstallMetamodAsync(cs2Path);
                }
                
                // Update CS2KZ if needed
                if (!status.CS2KZInstalled || status.CS2KZUpdateAvailable || status.MappingAPIUpdateAvailable)
                {
                    await DownloadAndInstallCS2KZAsync(cs2Path);
                }
                
                StatusChanged?.Invoke(this, "All updates completed");
                return true;
            }
            catch (Exception ex)
            {
                StatusChanged?.Invoke(this, $"Error: {ex.Message}");
                return false;
            }
        }
        
        private async Task DownloadAndInstallMetamodAsync(string cs2Path)
        {
            try
            {
                StatusChanged?.Invoke(this, "Downloading Metamod...");
                DownloadProgressChanged?.Invoke(this, 0);
                
                using var client = new HttpClient();
                client.Timeout = TimeSpan.FromMinutes(5);
                
                var versionResponse = await client.GetStringAsync(METAMOD_VERSION_URL);
                string version = versionResponse.Trim();
                string downloadUrl = $"https://mms.alliedmods.net/mmsdrop/2.0/{version}";
                
                using var response = await client.GetAsync(downloadUrl, HttpCompletionOption.ResponseHeadersRead);
                response.EnsureSuccessStatusCode();
                
                long? totalBytes = response.Content.Headers.ContentLength;
                using var contentStream = await response.Content.ReadAsStreamAsync();
                using var memoryStream = new MemoryStream();
                
                var buffer = new byte[8192];
                long totalRead = 0;
                int bytesRead;
                
                while ((bytesRead = await contentStream.ReadAsync(buffer, 0, buffer.Length)) > 0)
                {
                    await memoryStream.WriteAsync(buffer, 0, bytesRead);
                    totalRead += bytesRead;
                    
                    if (totalBytes.HasValue && totalBytes.Value > 0)
                    {
                        int progress = (int)((totalRead * 100) / totalBytes.Value);
                        DownloadProgressChanged?.Invoke(this, progress);
                    }
                }
                
                StatusChanged?.Invoke(this, "Installing Metamod...");
                
                memoryStream.Position = 0;
                string outputPath = Path.Combine(cs2Path, "game", "csgo");
                
                using var archive = new ZipArchive(memoryStream, ZipArchiveMode.Read);
                archive.ExtractToDirectory(outputPath, overwriteFiles: true);
                
                // Save version
                var versions = LoadVersions();
                versions["metamod"] = version;
                SaveVersions(versions);
                
                StatusChanged?.Invoke(this, "Metamod installed successfully");
                DownloadProgressChanged?.Invoke(this, 100);
            }
            catch (Exception ex)
            {
                StatusChanged?.Invoke(this, $"Error installing Metamod: {ex.Message}");
                throw;
            }
        }
        
        private async Task DownloadAndInstallCS2KZAsync(string cs2Path)
        {
            try
            {
                StatusChanged?.Invoke(this, "Downloading CS2KZ plugin...");
                DownloadProgressChanged?.Invoke(this, 0);
                
                using var client = new HttpClient();
                client.DefaultRequestHeaders.Add("User-Agent", "CS2KZ-Mapping-Tools");
                client.Timeout = TimeSpan.FromMinutes(5);
                
                // Get latest release info
                var releaseResponse = await client.GetStringAsync(CS2KZ_API_URL);
                using var releaseDoc = JsonDocument.Parse(releaseResponse);
                
                string version = releaseDoc.RootElement.GetProperty("tag_name").GetString() ?? "";
                
                // Find the windows asset
                string? downloadUrl = null;
                foreach (var asset in releaseDoc.RootElement.GetProperty("assets").EnumerateArray())
                {
                    string name = asset.GetProperty("name").GetString() ?? "";
                    if (name == "cs2kz-windows-master.zip")
                    {
                        downloadUrl = asset.GetProperty("browser_download_url").GetString();
                        break;
                    }
                }
                
                if (string.IsNullOrEmpty(downloadUrl))
                {
                    throw new Exception("CS2KZ Windows package not found in release");
                }
                
                // Download CS2KZ
                using var response = await client.GetAsync(downloadUrl, HttpCompletionOption.ResponseHeadersRead);
                response.EnsureSuccessStatusCode();
                
                long? totalBytes = response.Content.Headers.ContentLength;
                using var contentStream = await response.Content.ReadAsStreamAsync();
                using var memoryStream = new MemoryStream();
                
                var buffer = new byte[8192];
                long totalRead = 0;
                int bytesRead;
                
                while ((bytesRead = await contentStream.ReadAsync(buffer, 0, buffer.Length)) > 0)
                {
                    await memoryStream.WriteAsync(buffer, 0, bytesRead);
                    totalRead += bytesRead;
                    
                    if (totalBytes.HasValue && totalBytes.Value > 0)
                    {
                        int progress = (int)((totalRead * 50) / totalBytes.Value); // First 50%
                        DownloadProgressChanged?.Invoke(this, progress);
                    }
                }
                
                StatusChanged?.Invoke(this, "Installing CS2KZ plugin...");
                
                memoryStream.Position = 0;
                string outputPath = Path.Combine(cs2Path, "game", "csgo");
                
                using var archive = new ZipArchive(memoryStream, ZipArchiveMode.Read);
                archive.ExtractToDirectory(outputPath, overwriteFiles: true);
                
                DownloadProgressChanged?.Invoke(this, 60);
                
                // Download mapping API
                StatusChanged?.Invoke(this, "Downloading Mapping API...");
                var mappingApiBytes = await client.GetByteArrayAsync(MAPPING_API_URL);
                
                string mappingApiPath = Path.Combine(cs2Path, "game", "csgo_core");
                Directory.CreateDirectory(mappingApiPath);
                
                string fgdPath = Path.Combine(mappingApiPath, "csgo_internal.fgd");
                await File.WriteAllBytesAsync(fgdPath, mappingApiBytes);
                
                string mappingApiHash = ComputeMD5Hash(mappingApiBytes);
                
                DownloadProgressChanged?.Invoke(this, 80);
                
                // Update time limit in config
                UpdateCS2KZTimeLimit(cs2Path);
                
                // Save versions
                var versions = LoadVersions();
                versions["cs2kz"] = version;
                versions["mapping_api"] = mappingApiHash;
                SaveVersions(versions);
                
                StatusChanged?.Invoke(this, "CS2KZ plugin installed successfully");
                DownloadProgressChanged?.Invoke(this, 100);
            }
            catch (Exception ex)
            {
                StatusChanged?.Invoke(this, $"Error installing CS2KZ: {ex.Message}");
                throw;
            }
        }
        
        private void UpdateCS2KZTimeLimit(string cs2Path)
        {
            try
            {
                string configPath = Path.Combine(cs2Path, "game", "csgo", "cfg", "cs2kz-server-config.txt");
                if (!File.Exists(configPath)) return;
                
                string content = File.ReadAllText(configPath);
                content = System.Text.RegularExpressions.Regex.Replace(
                    content,
                    @"(""defaultTimeLimit""\s+)""60\.0""",
                    @"$1""1440.0"""
                );
                
                File.WriteAllText(configPath, content);
            }
            catch
            {
                // Ignore errors in config update
            }
        }
        
        private System.Collections.Generic.Dictionary<string, string> LoadVersions()
        {
            var versions = new System.Collections.Generic.Dictionary<string, string>();
            
            try
            {
                if (File.Exists(_versionFile))
                {
                    foreach (var line in File.ReadAllLines(_versionFile))
                    {
                        if (line.Contains('='))
                        {
                            var parts = line.Split(new[] { '=' }, 2);
                            if (parts.Length == 2)
                            {
                                versions[parts[0]] = parts[1];
                            }
                        }
                    }
                }
            }
            catch { }
            
            return versions;
        }
        
        private void SaveVersions(System.Collections.Generic.Dictionary<string, string> versions)
        {
            try
            {
                var lines = new System.Collections.Generic.List<string>();
                foreach (var kvp in versions)
                {
                    lines.Add($"{kvp.Key}={kvp.Value}");
                }
                File.WriteAllLines(_versionFile, lines);
            }
            catch { }
        }
        
        private string ComputeMD5Hash(byte[] data)
        {
            using var md5 = MD5.Create();
            byte[] hash = md5.ComputeHash(data);
            var sb = new StringBuilder();
            foreach (byte b in hash)
            {
                sb.Append(b.ToString("x2"));
            }
            return sb.ToString();
        }
    }
    
    public class UpdateStatus
    {
        public bool MetamodInstalled { get; set; }
        public bool CS2KZInstalled { get; set; }
        public bool MetamodUpdateAvailable { get; set; }
        public bool CS2KZUpdateAvailable { get; set; }
        public bool MappingAPIUpdateAvailable { get; set; }
        public string MetamodCurrentVersion { get; set; } = "";
        public string MetamodLatestVersion { get; set; } = "";
        public string CS2KZCurrentVersion { get; set; } = "";
        public string CS2KZLatestVersion { get; set; } = "";
        public string MappingAPICurrentHash { get; set; } = "";
        public string MappingAPILatestHash { get; set; } = "";
        public string? Error { get; set; }
        
        public bool AnyUpdateAvailable => MetamodUpdateAvailable || CS2KZUpdateAvailable || MappingAPIUpdateAvailable;
    }
}
