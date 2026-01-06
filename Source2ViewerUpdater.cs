using System;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Net.Http;
using System.Text.Json;
using System.Threading.Tasks;

namespace CS2KZMappingTools
{
    public class Source2ViewerUpdater
    {
        private const string VERSION_CHECK_URL = "https://api.github.com/repos/ValveResourceFormat/ValveResourceFormat/commits/master";
        private const string DOWNLOAD_URL = "https://nightly.link/ValveResourceFormat/ValveResourceFormat/workflows/build/master/Source2Viewer.zip";
        
        private readonly string _basePath;
        private readonly string _installDir;
        private readonly string _appExecutable;
        private readonly string _versionFile;
        private readonly string _downloadFlagFile;
        private int _lastLoggedProgress = -1;
        
        public event EventHandler<int>? DownloadProgressChanged;
        public event EventHandler<string>? StatusChanged;
        
        public Source2ViewerUpdater()
        {
            _basePath = Path.Combine(Path.GetTempPath(), ".CS2KZ-mapping-tools");
            Directory.CreateDirectory(_basePath);
            
            _installDir = _basePath;
            _appExecutable = Path.Combine(_installDir, "Source2Viewer.exe");
            _versionFile = Path.Combine(_installDir, "cs2kz_versions.txt");
            _downloadFlagFile = Path.Combine(_basePath, ".s2v_downloading");
        }
        
        public bool IsDownloading()
        {
            return File.Exists(_downloadFlagFile);
        }
        
        public async Task<string?> GetRemoteVersionAsync()
        {
            try
            {
                StatusChanged?.Invoke(this, "Checking remote version...");
                
                using var client = new HttpClient();
                client.DefaultRequestHeaders.Add("User-Agent", "CS2KZ-Mapping-Tools");
                client.Timeout = TimeSpan.FromSeconds(10);
                
                var response = await client.GetStringAsync(VERSION_CHECK_URL);
                using var doc = JsonDocument.Parse(response);
                
                if (doc.RootElement.TryGetProperty("sha", out var shaElement))
                {
                    string fullSha = shaElement.GetString() ?? "";
                    string version = fullSha.Substring(0, Math.Min(8, fullSha.Length)).ToUpper();
                    StatusChanged?.Invoke(this, $"Remote version: {version}");
                    return version;
                }
                
                return null;
            }
            catch (HttpRequestException ex) when (ex.Message.Contains("403"))
            {
                StatusChanged?.Invoke(this, "GitHub API rate limit exceeded. Will try again later.");
                return null;
            }
            catch (Exception ex)
            {
                StatusChanged?.Invoke(this, $"Error checking version: {ex.Message}");
                return null;
            }
        }
        
        public string GetLocalVersion()
        {
            // First try to read from version file
            if (File.Exists(_versionFile))
            {
                try
                {
                    foreach (var line in File.ReadAllLines(_versionFile))
                    {
                        if (line.Contains('='))
                        {
                            var parts = line.Split(new[] { '=' }, 2);
                            if (parts.Length == 2 && parts[0].Trim() == "source2viewer")
                            {
                                string version = parts[1].Trim();
                                if (!string.IsNullOrEmpty(version) && version != "0")
                                {
                                    // Check if exe actually exists - if not, consider it not installed
                                    if (File.Exists(_appExecutable))
                                    {
                                        StatusChanged?.Invoke(this, $"Local version from file: {version}");
                                        return version;
                                    }
                                    else
                                    {
                                        StatusChanged?.Invoke(this, "Version file exists but executable not found - considering not installed");
                                        // Remove stale version info from file
                                        try
                                        {
                                            var lines = File.ReadAllLines(_versionFile).ToList();
                                            lines.RemoveAll(line => line.StartsWith("source2viewer=") || line.StartsWith("source2viewer_latest="));
                                            File.WriteAllLines(_versionFile, lines);
                                        }
                                        catch { }
                                        return "0";
                                    }
                                }
                            }
                        }
                    }
                }
                catch (Exception ex)
                {
                    StatusChanged?.Invoke(this, $"Error reading version file: {ex.Message}");
                }
            }
            
            if (!File.Exists(_appExecutable))
            {
                StatusChanged?.Invoke(this, "No local installation found");
                return "0";
            }
            
            try
            {
                var versionInfo = FileVersionInfo.GetVersionInfo(_appExecutable);
                string? productVersion = versionInfo.ProductVersion;
                
                StatusChanged?.Invoke(this, $"Reading exe ProductVersion: {productVersion ?? "null"}");
                
                if (!string.IsNullOrEmpty(productVersion))
                {
                    // Try to extract SHA - could be "1.0.0+abc12345" or just "abc12345"
                    string sha = productVersion!;
                    
                    // If it has a + sign, take everything after it
                    int plusIndex = sha.IndexOf('+');
                    if (plusIndex >= 0 && plusIndex + 1 < sha.Length)
                    {
                        sha = sha.Substring(plusIndex + 1);
                    }
                    
                    // Clean up the SHA - take first 8 characters
                    sha = sha.Trim();
                    if (sha.Length >= 6)
                    {
                        string version = sha.Substring(0, Math.Min(8, sha.Length)).ToUpper();
                        StatusChanged?.Invoke(this, $"Local version: {version}");
                        return version;
                    }
                }
                
                // If executable exists but we can't parse version
                StatusChanged?.Invoke(this, "Could not parse local version from exe");
                return "0";
            }
            catch (Exception ex)
            {
                StatusChanged?.Invoke(this, $"Error reading version: {ex.Message}");
                return "0";
            }
        }
        
        public async Task<bool> DownloadAndInstallAsync(string newVersion)
        {
            try
            {
                // Create download flag
                File.WriteAllText(_downloadFlagFile, "1");
                
                StatusChanged?.Invoke(this, "Downloading Source2Viewer...");
                DownloadProgressChanged?.Invoke(this, 0);
                _lastLoggedProgress = -1; // Reset progress tracking
                
                using var client = new HttpClient();
                client.Timeout = TimeSpan.FromMinutes(5);
                
                using var response = await client.GetAsync(DOWNLOAD_URL, HttpCompletionOption.ResponseHeadersRead);
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
                        if (progress != _lastLoggedProgress)
                        {
                            StatusChanged?.Invoke(this, $"Downloading... {progress}%");
                            _lastLoggedProgress = progress;
                        }
                    }
                }
                
                StatusChanged?.Invoke(this, "Extracting files...");
                DownloadProgressChanged?.Invoke(this, 100);
                
                // Remove old executable
                if (File.Exists(_appExecutable))
                {
                    try
                    {
                        File.Delete(_appExecutable);
                    }
                    catch (Exception ex)
                    {
                        StatusChanged?.Invoke(this, $"Warning: Could not remove old exe: {ex.Message}");
                    }
                }
                
                // Extract zip
                memoryStream.Position = 0;
                using (var archive = new ZipArchive(memoryStream, ZipArchiveMode.Read))
                {
                    archive.ExtractToDirectory(_installDir, overwriteFiles: true);
                }
                
                // Delete XML file if exists
                string xmlFile = Path.Combine(_installDir, "ValveResourceFormat.xml");
                if (File.Exists(xmlFile))
                {
                    try
                    {
                        File.Delete(xmlFile);
                    }
                    catch { }
                }
                
                // Save version info
                SaveVersionInfo(newVersion);
                
                StatusChanged?.Invoke(this, "Update complete!");
                
                // Remove download flag
                if (File.Exists(_downloadFlagFile))
                {
                    File.Delete(_downloadFlagFile);
                }
                
                return true;
            }
            catch (Exception ex)
            {
                StatusChanged?.Invoke(this, $"Error during update: {ex.Message}");
                
                // Remove download flag on error
                if (File.Exists(_downloadFlagFile))
                {
                    File.Delete(_downloadFlagFile);
                }
                
                return false;
            }
        }
        
        private void SaveVersionInfo(string version)
        {
            try
            {
                var versions = new System.Collections.Generic.Dictionary<string, string>();
                
                // Read existing versions
                if (File.Exists(_versionFile))
                {
                    foreach (var line in File.ReadAllLines(_versionFile))
                    {
                        if (line.Contains('='))
                        {
                            var parts = line.Split(new[] { '=' }, 2);
                            if (parts.Length == 2)
                            {
                                versions[parts[0].Trim()] = parts[1].Trim();
                            }
                        }
                    }
                }
                
                // Update Source2Viewer version
                versions["source2viewer"] = version;
                versions["source2viewer_latest"] = version;
                
                // Write back
                var lines = new System.Collections.Generic.List<string>();
                foreach (var kvp in versions)
                {
                    lines.Add($"{kvp.Key}={kvp.Value}");
                }
                File.WriteAllLines(_versionFile, lines);
            }
            catch { }
        }
        
        public bool LaunchApp()
        {
            if (!File.Exists(_appExecutable))
            {
                StatusChanged?.Invoke(this, "Source2Viewer not found");
                return false;
            }
            
            try
            {
                StatusChanged?.Invoke(this, "Launching Source2Viewer...");
                Process.Start(new ProcessStartInfo
                {
                    FileName = _appExecutable,
                    UseShellExecute = true,
                    WorkingDirectory = _installDir
                });
                return true;
            }
            catch (Exception ex)
            {
                StatusChanged?.Invoke(this, $"Error launching: {ex.Message}");
                return false;
            }
        }
        
        public async Task<bool> UpdateAndLaunchAsync()
        {
            string? remoteVersion = await GetRemoteVersionAsync();
            string localVersion = GetLocalVersion();
            
            // If remote version check fails but S2V is installed, just launch it
            if (remoteVersion == null)
            {
                if (localVersion != "0")
                {
                    StatusChanged?.Invoke(this, "Cannot check for updates, launching existing version");
                    return LaunchApp();
                }
                else
                {
                    StatusChanged?.Invoke(this, "Cannot download: GitHub API unavailable (rate limit). Please try again later.");
                    return false;
                }
            }
            
            if (remoteVersion != localVersion)
            {
                StatusChanged?.Invoke(this, $"Update needed: {localVersion} -> {remoteVersion}");
                bool success = await DownloadAndInstallAsync(remoteVersion);
                if (!success)
                {
                    return false;
                }
            }
            else
            {
                StatusChanged?.Invoke(this, "Already up to date");
                SaveVersionInfo(localVersion);
            }
            
            return LaunchApp();
        }
    }
}
