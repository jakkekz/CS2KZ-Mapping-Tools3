using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Imaging;
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using System.Threading.Tasks;
using System.Windows.Forms;
using Microsoft.Win32;

#nullable enable

namespace CS2KZMappingTools
{
    public partial class LoadingScreenForm : Form
    {
        private readonly ThemeManager _themeManager;
        public event Action<string>? LogMessage;
        private ComboBox? _addonNameComboBox;
        private ComboBox? _mapNameComboBox;
        private Button? _selectImagesButton;
        private Label? _clearImagesButton;
        private Label? _imagesPathLabel;
        private Button? _selectIconButton;
        private Label? _clearIconButton;
        private Label? _iconPathLabel;
        private TextBox? _descriptionTextBox;
        private Button? _createButton;
        private Button? _closeButton;
        private ProgressBar? _progressBar;
        private Label? _statusLabel;
        private Label? _helpLabel;
        private Label? _imagesStatusLabel;
        private Label? _iconStatusLabel;
        private Label? _descriptionStatusLabel;

        private List<string> _imageFiles = new List<string>();
        private string _iconFile = "";
        private string _cs2Path = "";

        public LoadingScreenForm(ThemeManager themeManager)
        {
            _themeManager = themeManager;
            InitializeComponent();
            FindCs2Path();
            // Populate dropdowns after finding CS2 path
            PopulateAddonDropdown();
            PopulateMapDropdown();
            ApplyTheme();
            UpdateStatus(); // Call after ApplyTheme to set status colors
        }

        private void ApplyTheme()
        {
            var theme = _themeManager.GetCurrentTheme();
            
            // Apply theme to form
            BackColor = theme.WindowBackground;
            ForeColor = theme.Text;

            // Apply theme to controls
            foreach (Control control in Controls)
            {
                ApplyThemeToControl(control);
            }
        }

        private void ApplyThemeToControl(Control control)
        {
            var theme = _themeManager.GetCurrentTheme();
            
            if (control is TextBox textBox)
            {
                textBox.BackColor = theme.ButtonBackground;
                textBox.ForeColor = theme.Text;
            }
            else if (control is ComboBox comboBox)
            {
                comboBox.BackColor = theme.ButtonBackground;
                comboBox.ForeColor = theme.Text;
            }
            else if (control is Button button)
            {
                button.BackColor = theme.ButtonBackground;
                button.ForeColor = theme.Text;
                button.FlatStyle = FlatStyle.Flat;
                button.FlatAppearance.BorderColor = theme.Border;
            }
            else if (control is Label label)
            {
                label.ForeColor = theme.Text;
            }
            else if (control is RichTextBox richTextBox)
            {
                richTextBox.BackColor = Color.FromArgb(45, 45, 45);
                richTextBox.ForeColor = Color.LightGray;
            }
            else if (control is ProgressBar progressBar)
            {
                progressBar.BackColor = theme.WindowBackground;
                progressBar.ForeColor = theme.AccentColor;
            }

            // Apply recursively to child controls
            foreach (Control child in control.Controls)
            {
                ApplyThemeToControl(child);
            }
        }

        private void InitializeComponent()
        {
            this.Text = "CS2 Loading Screen Creator";
            this.Size = new Size(550, 460);
            this.StartPosition = FormStartPosition.CenterScreen;
            this.FormBorderStyle = FormBorderStyle.FixedDialog;
            this.MaximizeBox = false;
            this.MinimizeBox = false;
            this.Padding = new Padding(20);
            this.Font = new Font("Segoe UI", 9F);

            // Title
            var titleLabel = new Label
            {
                Text = "Loading Screen Creator",
                Location = new Point(0, 0),
                Size = new Size(510, 30),
                Font = new Font("Segoe UI", 14F, FontStyle.Bold),
                TextAlign = ContentAlignment.MiddleCenter
            };

            // Addon Name
            var addonLabel = new Label
            {
                Text = "Addon:",
                Location = new Point(0, 50),
                Size = new Size(80, 20)
            };

            _addonNameComboBox = new ComboBox
            {
                Location = new Point(90, 45),
                Size = new Size(400, 25),
                DropDownStyle = ComboBoxStyle.DropDownList,
                Font = new Font("Segoe UI", 9F)
            };
            _addonNameComboBox.SelectedIndexChanged += AddonNameComboBox_SelectedIndexChanged;

            // Map Name
            var mapLabel = new Label
            {
                Text = "Map:",
                Location = new Point(0, 85),
                Size = new Size(80, 20)
            };

            _mapNameComboBox = new ComboBox
            {
                Location = new Point(90, 80),
                Size = new Size(400, 25),
                DropDownStyle = ComboBoxStyle.DropDownList,
                Font = new Font("Segoe UI", 9F)
            };

            // Loading Screen Images
            var imagesLabel = new Label
            {
                Text = "Loading Screen Images:",
                Location = new Point(0, 120),
                Size = new Size(140, 20),
                Font = new Font("Segoe UI", 9F, FontStyle.Bold)
            };

            _selectImagesButton = new Button
            {
                Text = "Select Images (1-9)...",
                Location = new Point(150, 115),
                Size = new Size(120, 30),
                FlatStyle = FlatStyle.Flat,
                Font = new Font("Segoe UI", 9F)
            };
            _selectImagesButton.Click += SelectImagesButton_Click;

            _clearImagesButton = new Label
            {
                Text = "clear",
                Location = new Point(470, 120),
                Size = new Size(40, 20),
                Font = new Font("Segoe UI", 8F, FontStyle.Underline),
                Cursor = Cursors.Hand,
                TextAlign = ContentAlignment.MiddleLeft
            };
            _clearImagesButton.Click += (s, e) => {
                _imageFiles.Clear();
                _imagesPathLabel.Text = "No file selected";
                LogToEvent("Cleared selected images");
                UpdateStatus();
            };

            _imagesPathLabel = new Label
            {
                Text = "No file selected",
                Location = new Point(280, 120),
                Size = new Size(210, 20),
                Font = new Font("Segoe UI", 8F)
            };

            // Map Icon (SVG)
            var iconLabel = new Label
            {
                Text = "Map Icon (SVG):",
                Location = new Point(0, 155),
                Size = new Size(140, 20),
                Font = new Font("Segoe UI", 9F, FontStyle.Bold)
            };

            _selectIconButton = new Button
            {
                Text = "Browse File...",
                Location = new Point(150, 150),
                Size = new Size(120, 30),
                FlatStyle = FlatStyle.Flat,
                Font = new Font("Segoe UI", 9F)
            };
            _selectIconButton.Click += SelectIconButton_Click;

            _clearIconButton = new Label
            {
                Text = "clear",
                Location = new Point(470, 155),
                Size = new Size(40, 20),
                Font = new Font("Segoe UI", 8F, FontStyle.Underline),
                Cursor = Cursors.Hand,
                TextAlign = ContentAlignment.MiddleLeft
            };
            _clearIconButton.Click += (s, e) => {
                _iconFile = "";
                _iconPathLabel.Text = "No file selected";
                LogToEvent("Cleared selected icon");
                UpdateStatus();
            };

            _iconPathLabel = new Label
            {
                Text = "No file selected",
                Location = new Point(280, 155),
                Size = new Size(210, 20),
                Font = new Font("Segoe UI", 8F)
            };

            // Map Description
            var descriptionLabel = new Label
            {
                Text = "Map Description:",
                Location = new Point(0, 190),
                Size = new Size(140, 20),
                Font = new Font("Segoe UI", 9F, FontStyle.Bold)
            };

            _descriptionTextBox = new TextBox
            {
                Location = new Point(0, 215),
                Size = new Size(510, 80),
                Multiline = true,
                ScrollBars = ScrollBars.Vertical,
                Font = new Font("Segoe UI", 9F),
                PlaceholderText = "Enter map description here..."
            };
            _descriptionTextBox.TextChanged += (s, e) => UpdateStatus();

            // Progress Bar
            _progressBar = new ProgressBar
            {
                Location = new Point(0, 270),
                Size = new Size(510, 25),
                Style = ProgressBarStyle.Continuous,
                Visible = false
            };

            // Status Labels
            _statusLabel = new Label
            {
                Text = "Select addon, map, and at least one item to get started",
                Location = new Point(0, 305),
                Size = new Size(510, 20),
                TextAlign = ContentAlignment.MiddleCenter,
                Font = new Font("Segoe UI", 9F)
            };

            _helpLabel = new Label
            {
                Text = "Run map (without compile) to test.",
                Location = new Point(0, 325),
                Size = new Size(510, 20),
                TextAlign = ContentAlignment.MiddleCenter,
                Font = new Font("Segoe UI", 8F),
                ForeColor = Color.Gray,
                Visible = false
            };

            _imagesStatusLabel = new Label
            {
                Text = "Images: ✗",
                Location = new Point(100, 350),
                Size = new Size(100, 20),
                TextAlign = ContentAlignment.MiddleCenter,
                Font = new Font("Segoe UI", 9F),
                ForeColor = Color.Red
            };

            _iconStatusLabel = new Label
            {
                Text = "Icon: ✗",
                Location = new Point(205, 350),
                Size = new Size(100, 20),
                TextAlign = ContentAlignment.MiddleCenter,
                Font = new Font("Segoe UI", 9F),
                ForeColor = Color.Red
            };

            _descriptionStatusLabel = new Label
            {
                Text = "Description: ✗",
                Location = new Point(310, 350),
                Size = new Size(100, 20),
                TextAlign = ContentAlignment.MiddleCenter,
                Font = new Font("Segoe UI", 9F),
                ForeColor = Color.Red
            };

            // Buttons
            _createButton = new Button
            {
                Text = "Create",
                Location = new Point(195, 380),
                Size = new Size(120, 35),
                FlatStyle = FlatStyle.Flat,
                Font = new Font("Segoe UI", 9F, FontStyle.Bold),
                Enabled = false
            };
            _createButton.Click += CreateButton_Click;

            _closeButton = new Button
            {
                Text = "Close",
                Location = new Point(300, 365),
                Size = new Size(100, 35),
                FlatStyle = FlatStyle.Flat,
                Font = new Font("Segoe UI", 9F),
                Visible = false
            };
            _closeButton.Click += (s, e) => this.Close();

            // Add controls
            this.Controls.AddRange(new Control[] {
                titleLabel,
                addonLabel, _addonNameComboBox,
                mapLabel, _mapNameComboBox,
                imagesLabel, _selectImagesButton, _clearImagesButton, _imagesPathLabel,
                iconLabel, _selectIconButton, _clearIconButton, _iconPathLabel,
                descriptionLabel, _descriptionTextBox,
                _progressBar, _statusLabel, _helpLabel,
                _imagesStatusLabel, _iconStatusLabel, _descriptionStatusLabel,
                _createButton, _closeButton
            });
        }

        private void SelectImagesButton_Click(object? sender, EventArgs e)
        {
            using var dialog = new OpenFileDialog
            {
                Title = "Select Loading Screen Images (1-9 images)",
                Filter = "Image files (*.jpg;*.jpeg;*.png;*.bmp)|*.jpg;*.jpeg;*.png;*.bmp|All files (*.*)|*.*",
                Multiselect = true,
                CheckFileExists = true
            };

            if (dialog.ShowDialog() == DialogResult.OK)
            {
                var selectedFiles = dialog.FileNames.ToList();
                
                if (selectedFiles.Count > 9)
                {
                    MessageBox.Show("Please select a maximum of 9 images.", "Too Many Images", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                    return;
                }
                
                // If only 1 image is selected, duplicate it to meet CS2's minimum requirement of 2
                if (selectedFiles.Count == 1)
                {
                    _imageFiles = new List<string> { selectedFiles[0], selectedFiles[0] };
                    LogToEvent($"Selected 1 image (duplicated for CS2 requirement): {Path.GetFileName(selectedFiles[0])}");
                    _imagesPathLabel.Text = $"1 image (duplicated)";
                }
                else
                {
                    _imageFiles = selectedFiles;
                    LogToEvent($"Selected {_imageFiles.Count} images");
                    _imagesPathLabel.Text = $"{_imageFiles.Count} images selected";
                }
                
                UpdateStatus();
            }
        }

        private void SelectIconButton_Click(object? sender, EventArgs e)
        {
            using var dialog = new OpenFileDialog
            {
                Title = "Select Map Icon SVG File",
                Filter = "SVG files (*.svg)|*.svg|All files (*.*)|*.*",
                CheckFileExists = true
            };

            if (dialog.ShowDialog() == DialogResult.OK)
            {
                _iconFile = dialog.FileName;
                _iconPathLabel.Text = Path.GetFileName(_iconFile);
                LogToEvent($"Selected icon file: {_iconFile}");
                UpdateStatus();
            }
        }

        private void AddonNameComboBox_SelectedIndexChanged(object? sender, EventArgs e)
        {
            PopulateMapDropdown();
            UpdateStatus();
        }

        private async void CreateButton_Click(object? sender, EventArgs e)
        {
            if (_addonNameComboBox.SelectedItem == null)
            {
                MessageBox.Show("Please select an addon.", "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return;
            }

            if (_mapNameComboBox.SelectedItem == null)
            {
                MessageBox.Show("Please select a map.", "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return;
            }

            // Check if at least one of images, icon, or description is provided
            bool hasImages = _imageFiles.Count > 0;
            bool hasIcon = !string.IsNullOrEmpty(_iconFile);
            bool hasDescription = !string.IsNullOrWhiteSpace(_descriptionTextBox?.Text);

            if (!hasImages && !hasIcon && !hasDescription)
            {
                MessageBox.Show("Please provide at least one of the following: loading screen images, map icon, or map description.", "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return;
            }

            if (string.IsNullOrEmpty(_cs2Path))
            {
                MessageBox.Show("Could not find CS2 installation. Please make sure CS2 is installed.", "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return;
            }

            _createButton.Enabled = false;
            _progressBar.Visible = true;
            _progressBar.Value = 0;

            try
            {
                await CreateLoadingScreenAsync(_addonNameComboBox.SelectedItem.ToString()!, _mapNameComboBox.SelectedItem.ToString()!, _imageFiles, _iconFile, _descriptionTextBox.Text);
                LogToEvent("Loading screen creation completed successfully!");
                _statusLabel.Text = "Completed successfully!";
                _helpLabel.Visible = true;
            }
            catch (Exception ex)
            {
                LogToEvent($"Error: {ex.Message}");
                _statusLabel.Text = "Error occurred";
                MessageBox.Show($"An error occurred: {ex.Message}", "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
            finally
            {
                _createButton.Enabled = true;
                _progressBar.Visible = false;
            }
        }

        private void LogToEvent(string message)
        {
            LogMessage?.Invoke($"[LoadingScreen] {message}");
        }

        private void FindCs2Path()
        {
            try
            {
                // Get Steam path from registry
                using var key = Registry.CurrentUser.OpenSubKey(@"Software\Valve\Steam");
                if (key?.GetValue("SteamPath") is string steamPath)
                {
                    // Try both casings for libraryfolders.vdf
                    var libraryFoldersPath = Path.Combine(steamPath, "steamapps", "libraryfolders.vdf");
                    if (!File.Exists(libraryFoldersPath))
                    {
                        libraryFoldersPath = Path.Combine(steamPath, "SteamApps", "libraryfolders.vdf");
                    }
                    
                    _cs2Path = FindCs2LibraryPath(libraryFoldersPath);

                    if (!string.IsNullOrEmpty(_cs2Path))
                    {
                        // Try both casings for appmanifest
                        var appManifestPath = Path.Combine(_cs2Path, "steamapps", "appmanifest_730.acf");
                        if (!File.Exists(appManifestPath))
                        {
                            appManifestPath = Path.Combine(_cs2Path, "SteamApps", "appmanifest_730.acf");
                        }
                        
                        if (File.Exists(appManifestPath))
                        {
                            // Parse the VDF file to get install directory
                            var installDir = ParseAppManifest(appManifestPath);
                            if (!string.IsNullOrEmpty(installDir))
                            {
                                // Try both casings for common folder
                                _cs2Path = Path.Combine(_cs2Path, "steamapps", "common", installDir);
                                if (!Directory.Exists(_cs2Path))
                                {
                                    _cs2Path = Path.Combine(_cs2Path.Replace("steamapps", "SteamApps"), installDir);
                                }
                                LogToEvent($"Found CS2 at: {_cs2Path}");
                                return;
                            }
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                LogToEvent($"Error finding CS2 path: {ex.Message}");
            }

            LogToEvent("Could not find CS2 installation automatically");
        }

        private void PopulateAddonDropdown()
        {
            _addonNameComboBox.Items.Clear();
            
            if (!string.IsNullOrEmpty(_cs2Path))
            {
                // Look in content/csgo_addons instead of game/csgo_addons
                var addonsPath = Path.Combine(_cs2Path, "content", "csgo_addons");
                if (Directory.Exists(addonsPath))
                {
                    var addonDirs = Directory.GetDirectories(addonsPath)
                        .Select(Path.GetFileName)
                        .Where(name => !string.IsNullOrEmpty(name) && 
                                      !name.Equals("addon_template", StringComparison.OrdinalIgnoreCase) &&
                                      !name.Equals("addontemplate", StringComparison.OrdinalIgnoreCase))
                        .OrderBy(name => name)
                        .ToArray();
                    
                    _addonNameComboBox.Items.AddRange(addonDirs.Cast<object>().ToArray());
                    
                    if (addonDirs.Length > 0)
                    {
                        _addonNameComboBox.SelectedIndex = 0;
                    }
                    
                    LogToEvent($"Found {addonDirs.Length} addons in {addonsPath}");
                }
                else
                {
                    LogToEvent($"Addons directory not found: {addonsPath}");
                }
            }
        }

        private void PopulateMapDropdown()
        {
            _mapNameComboBox.Items.Clear();
            
            if (!string.IsNullOrEmpty(_cs2Path) && _addonNameComboBox.SelectedItem != null)
            {
                var addonName = _addonNameComboBox.SelectedItem!.ToString();
                // Maps are in the addon's maps folder
                var mapsPath = Path.Combine(_cs2Path, "content", "csgo_addons", addonName, "maps");
                if (Directory.Exists(mapsPath))
                {
                    var mapFiles = Directory.GetFiles(mapsPath, "*.vmap")
                        .Select(Path.GetFileNameWithoutExtension)
                        .OrderBy(name => name)
                        .ToArray();
                    
                    _mapNameComboBox.Items.AddRange(mapFiles.Cast<object>().ToArray());
                    
                    if (mapFiles.Length > 0)
                    {
                        _mapNameComboBox.SelectedIndex = 0;
                    }
                    
                    LogToEvent($"Found {mapFiles.Length} maps in {mapsPath}");
                }
                else
                {
                    LogToEvent($"Maps directory not found: {mapsPath}");
                }
            }
        }

        private string? FindCs2LibraryPath(string libraryFoldersPath)
        {
            if (!File.Exists(libraryFoldersPath)) return null;

            try
            {
                // Check default Steam location first
                var steamPath = Path.GetDirectoryName(Path.GetDirectoryName(libraryFoldersPath));
                if (!string.IsNullOrEmpty(steamPath))
                {
                    var defaultManifest = Path.Combine(steamPath, "steamapps", "appmanifest_730.acf");
                    if (!File.Exists(defaultManifest))
                    {
                        defaultManifest = Path.Combine(steamPath, "SteamApps", "appmanifest_730.acf");
                    }
                    if (File.Exists(defaultManifest))
                    {
                        return steamPath;
                    }
                }
                
                // Check all library folders
                var content = File.ReadAllText(libraryFoldersPath);
                var lines = content.Split('\n');
                
                foreach (var line in lines)
                {
                    var trimmed = line.Trim();
                    if (trimmed.Contains("\"path\""))
                    {
                        var match = Regex.Match(trimmed, "\"path\"\\s+\"([^\"]+)\"");
                        if (match.Success)
                        {
                            var libraryPath = match.Groups[1].Value.Replace("\\\\", "\\");
                            
                            // Check if this library has CS2
                            var manifestPath = Path.Combine(libraryPath, "steamapps", "appmanifest_730.acf");
                            if (!File.Exists(manifestPath))
                            {
                                manifestPath = Path.Combine(libraryPath, "SteamApps", "appmanifest_730.acf");
                            }
                            
                            if (File.Exists(manifestPath))
                            {
                                return libraryPath;
                            }
                        }
                    }
                }
            }
            catch { }

            return null;
        }

        private string? ParseAppManifest(string appManifestPath)
        {
            try
            {
                var content = File.ReadAllText(appManifestPath);
                var match = Regex.Match(content, "\"installdir\"\\s+\"([^\"]+)\"");
                return match.Success ? match.Groups[1].Value : null;
            }
            catch { }
            return null;
        }

        private void UpdateStatus()
        {
            var statusParts = new List<string>();
            
            if (_addonNameComboBox.SelectedItem != null)
                statusParts.Add("Addon: ✓");
            else
                statusParts.Add("Addon: ✗");
                
            if (_mapNameComboBox.SelectedItem != null)
                statusParts.Add("Map: ✓");
            else
                statusParts.Add("Map: ✗");
            
            // Check if at least one content item is selected
            bool hasImages = _imageFiles.Count > 0;
            bool hasIcon = !string.IsNullOrEmpty(_iconFile);
            bool hasDescription = !string.IsNullOrWhiteSpace(_descriptionTextBox?.Text);
            bool hasAnyContent = hasImages || hasIcon || hasDescription;
            
            // Update Images status
            if (hasImages)
            {
                _imagesStatusLabel.Text = "Images: ✓";
                _imagesStatusLabel.ForeColor = Color.Lime;
            }
            else
            {
                _imagesStatusLabel.Text = "Images: ✗";
                _imagesStatusLabel.ForeColor = hasAnyContent ? Color.Yellow : Color.Red;
            }
            
            // Update Icon status
            if (hasIcon)
            {
                _iconStatusLabel.Text = "Icon: ✓";
                _iconStatusLabel.ForeColor = Color.Lime;
            }
            else
            {
                _iconStatusLabel.Text = "Icon: ✗";
                _iconStatusLabel.ForeColor = hasAnyContent ? Color.Yellow : Color.Red;
            }
            
            // Update Description status
            if (hasDescription)
            {
                _descriptionStatusLabel.Text = "Description: ✓";
                _descriptionStatusLabel.ForeColor = Color.Lime;
            }
            else
            {
                _descriptionStatusLabel.Text = "Description: ✗";
                _descriptionStatusLabel.ForeColor = hasAnyContent ? Color.Yellow : Color.Red;
            }
            
            // Enable create button if addon and map are selected, and at least one of images/icon/description is provided
            bool hasContent = _imageFiles.Count > 0 || 
                             !string.IsNullOrEmpty(_iconFile) || 
                             !string.IsNullOrWhiteSpace(_descriptionTextBox?.Text);
            
            _createButton.Enabled = _addonNameComboBox.SelectedItem != null &&
                                   _mapNameComboBox.SelectedItem != null &&
                                   hasContent;
        }

        private async Task CreateLoadingScreenAsync(string addonName, string mapName, List<string> imageFiles, string iconFile, string descriptionText)
        {
            LogToEvent("Starting loading screen creation...");

            // Use provided image files (already validated)
            if (!imageFiles.Any())
            {
                throw new Exception("No image files provided");
            }

            LogToEvent($"Using {imageFiles.Count} image files");

            // Create directories
            var gameRoot = _cs2Path;
            var gameAddonsDir = Path.Combine(gameRoot, "game", "csgo_addons", addonName);
            var contentAddonsDir = Path.Combine(gameRoot, "content", "csgo_addons", addonName);
            var loadingScreenDir = Path.Combine(contentAddonsDir, "panorama", "images", "map_icons", "screenshots", "1080p");
            var mapIconContentDir = Path.Combine(contentAddonsDir, "panorama", "images", "map_icons");
            var mapsDir = Path.Combine(gameAddonsDir, "maps");

            Directory.CreateDirectory(loadingScreenDir);
            Directory.CreateDirectory(mapIconContentDir);
            Directory.CreateDirectory(mapsDir);

            var vmatFilesToCompile = new List<string>();
            var svgFilesToCompile = new List<string>();

            // Process images (CS2 loading screens numbered 1-9 only)
            for (int i = 0; i < Math.Min(imageFiles.Count, 9); i++)
            {
                var sourceImagePath = imageFiles[i];
                var sourceImageName = Path.GetFileName(sourceImagePath);
                var imageIndex = i + 1; // CS2 expects loading screen indices 1-9

                LogToEvent($"Processing image {imageIndex}: {sourceImageName}");

                try
                {
                    var destImageName = $"{mapName}_{imageIndex}_png.png";
                    var destImagePath = Path.Combine(loadingScreenDir, destImageName);

                    // Check if source and destination are the same - skip if so to avoid file locking
                    if (Path.GetFullPath(sourceImagePath).Equals(Path.GetFullPath(destImagePath), StringComparison.OrdinalIgnoreCase))
                    {
                        LogToEvent($"Skipping {sourceImageName} - already at destination");
                        
                        // Still need to generate VMAT file
                        var skipVmatName = $"{mapName}_{imageIndex}_png.vmat";
                        var skipVmatPath = Path.Combine(loadingScreenDir, skipVmatName);
                        var skipVmatContent = CreateVmatContent(mapName, imageIndex);
                        await File.WriteAllTextAsync(skipVmatPath, skipVmatContent);
                        LogToEvent($"Generated VMAT file: {skipVmatName}");
                        vmatFilesToCompile.Add(skipVmatPath);
                        continue;
                    }

                    // Process image in a separate scope to ensure all handles are released
                    // First, load the source image into memory completely
                    byte[] imageData;
                    using (var fs = new FileStream(sourceImagePath, FileMode.Open, FileAccess.Read, FileShare.Read))
                    {
                        imageData = new byte[fs.Length];
                        await fs.ReadAsync(imageData, 0, imageData.Length);
                    }

                    // Now process from memory to avoid file locks
                    using (var ms = new MemoryStream(imageData))
                    using (var originalImage = Image.FromStream(ms))
                    {
                        // Calculate 16:9 dimensions
                        int targetWidth = 1920;
                        int targetHeight = 1080;

                        using (var resizedImage = new Bitmap(targetWidth, targetHeight))
                        {
                            using (var graphics = Graphics.FromImage(resizedImage))
                            {
                                graphics.InterpolationMode = System.Drawing.Drawing2D.InterpolationMode.HighQualityBicubic;
                                graphics.DrawImage(originalImage, 0, 0, targetWidth, targetHeight);
                            }

                            resizedImage.Save(destImagePath, ImageFormat.Png);
                        }
                    }
                    
                    LogToEvent($"Converted and saved {sourceImageName} to {destImagePath} (16:9 aspect ratio)");

                    // Generate VMAT file
                    var destVmatName = $"{mapName}_{imageIndex}_png.vmat";
                    var destVmatPath = Path.Combine(loadingScreenDir, destVmatName);
                    var vmatContent = CreateVmatContent(mapName, imageIndex);

                    await File.WriteAllTextAsync(destVmatPath, vmatContent);
                    LogToEvent($"Generated VMAT file: {destVmatName}");

                    vmatFilesToCompile.Add(destVmatPath);
                }
                catch (Exception ex)
                {
                    LogToEvent($"Error processing {sourceImageName}: {ex.Message}");
                }

                _progressBar.Value = (i + 1) * 40 / Math.Min(imageFiles.Count, 10);
            }

            // Process SVG file
            if (!string.IsNullOrEmpty(iconFile) && File.Exists(iconFile))
            {
                try
                {
                    var destIconName = $"map_icon_{mapName}.svg";
                    var destIconPath = Path.Combine(mapIconContentDir, destIconName);

                    // Use ReadAllBytes/WriteAllBytes to avoid file lock issues
                    var svgData = await File.ReadAllBytesAsync(iconFile);
                    await File.WriteAllBytesAsync(destIconPath, svgData);
                    
                    LogToEvent($"Copied SVG file to {destIconPath}");
                    svgFilesToCompile.Add(destIconPath);
                }
                catch (Exception ex)
                {
                    LogToEvent($"Error copying SVG file: {ex.Message}");
                }
            }
            else if (!string.IsNullOrEmpty(iconFile))
            {
                LogToEvent($"Warning: Selected SVG file not found: {iconFile}");
            }

            // Process description text
            if (!string.IsNullOrWhiteSpace(descriptionText))
            {
                var descriptionFileName = $"{mapName}.txt";
                var descriptionFilePath = Path.Combine(mapsDir, descriptionFileName);

                await File.WriteAllTextAsync(descriptionFilePath, descriptionText);
                LogToEvent($"Created description file at {descriptionFilePath}");
            }

            // Compile VMAT files
            if (vmatFilesToCompile.Any())
            {
                LogToEvent("Compiling VMAT files...");
                await CompileVmatFilesAsync(gameRoot, vmatFilesToCompile, mapName, addonName);
            }

            // Compile SVG files
            if (svgFilesToCompile.Any())
            {
                LogToEvent("Compiling SVG files...");
                await CompileSvgFilesAsync(gameRoot, svgFilesToCompile, mapName, addonName);
            }

            _progressBar.Value = 100;
            LogToEvent("Loading screen creation completed!");
        }

        private string CreateVmatContent(string mapName, int index)
        {
            // Use the correct path format for panorama images
            string texturePath = $"panorama/images/map_icons/screenshots/1080p/{mapName}_{index}_png.png";
            
            return $@"// THIS FILE IS AUTO-GENERATED

Layer0
{{
	shader ""csgo_composite_generic.vfx""

	g_flAlphaBlend ""0.000""

	//---- Options ----
	TextureA ""{texturePath}""
	TextureB """"

	Attributes
	{{
		TextureTiling ""1.000000 1.000000""
		TextureOffset ""0.000000 0.000000""
	}}


	VariableState
	{{
		""Options""
		{{
		}}
	}}
}}
";
        }

        private async Task CompileVmatFilesAsync(string gameRoot, List<string> vmatFiles, string mapName, string addonName)
        {
            var compilerPath = Path.Combine(gameRoot, "game", "bin", "win64", "resourcecompiler.exe");
            if (!File.Exists(compilerPath))
            {
                throw new Exception($"resourcecompiler.exe not found at {compilerPath}");
            }

            var compilerCwd = Path.Combine(gameRoot, "game");

            foreach (var vmatFile in vmatFiles)
            {
                LogToEvent($"Compiling {Path.GetFileName(vmatFile)}...");

                try
                {
                    var relativeVmatPath = Path.GetRelativePath(compilerCwd, vmatFile).Replace("\\", "/");

                    var process = Process.Start(new ProcessStartInfo
                    {
                        FileName = compilerPath,
                        Arguments = $"\"{relativeVmatPath}\"",
                        WorkingDirectory = compilerCwd,
                        UseShellExecute = false,
                        RedirectStandardOutput = true,
                        RedirectStandardError = true,
                        CreateNoWindow = true
                    });

                    if (process != null)
                    {
                        var output = await process.StandardOutput.ReadToEndAsync();
                        var error = await process.StandardError.ReadToEndAsync();
                        await process.WaitForExitAsync();

                        if (process.ExitCode == 0)
                        {
                            LogToEvent($"Compilation successful for {Path.GetFileName(vmatFile)}");
                        }
                        else
                        {
                            LogToEvent($"Compilation failed for {Path.GetFileName(vmatFile)}: {error}");
                            return; // Stop on first failure
                        }
                    }
                }
                catch (Exception ex)
                {
                    LogToEvent($"Error compiling {Path.GetFileName(vmatFile)}: {ex.Message}");
                    return;
                }
            }

            // Handle compiled files
            await HandleCompiledFilesAsync(gameRoot, mapName, addonName);
        }

        private async Task CompileSvgFilesAsync(string gameRoot, List<string> svgFiles, string mapName, string addonName)
        {
            var compilerPath = Path.Combine(gameRoot, "game", "bin", "win64", "resourcecompiler.exe");
            if (!File.Exists(compilerPath))
            {
                throw new Exception($"resourcecompiler.exe not found at {compilerPath}");
            }

            var compilerCwd = Path.Combine(gameRoot, "game");

            foreach (var svgFile in svgFiles)
            {
                LogToEvent($"Compiling {Path.GetFileName(svgFile)}...");

                try
                {
                    var relativeSvgPath = Path.GetRelativePath(compilerCwd, svgFile).Replace("\\", "/");

                    var process = Process.Start(new ProcessStartInfo
                    {
                        FileName = compilerPath,
                        Arguments = $"\"{relativeSvgPath}\"",
                        WorkingDirectory = compilerCwd,
                        UseShellExecute = false,
                        RedirectStandardOutput = true,
                        RedirectStandardError = true,
                        CreateNoWindow = true
                    });

                    if (process != null)
                    {
                        var output = await process.StandardOutput.ReadToEndAsync();
                        var error = await process.StandardError.ReadToEndAsync();
                        await process.WaitForExitAsync();

                        if (process.ExitCode == 0)
                        {
                            LogToEvent($"Compilation successful for {Path.GetFileName(svgFile)}");
                        }
                        else
                        {
                            LogToEvent($"Compilation failed for {Path.GetFileName(svgFile)}: {error}");
                            return; // Stop on first failure
                        }
                    }
                }
                catch (Exception ex)
                {
                    LogToEvent($"Error compiling {Path.GetFileName(svgFile)}: {ex.Message}");
                    return;
                }
            }
        }

        private Task HandleCompiledFilesAsync(string gameRoot, string mapName, string addonName)
        {
            LogToEvent("Handling compiled files...");

            var gameAddonsDir = Path.Combine(gameRoot, "game", "csgo_addons", addonName);
            var compiledScreenshotsDir = Path.Combine(gameAddonsDir, "panorama", "images", "map_icons", "screenshots", "1080p");
            var compiledIconsDir = Path.Combine(gameAddonsDir, "panorama", "images", "map_icons");

            // Handle compiled screenshot files (.vmat_c, .vtex_c)
            if (Directory.Exists(compiledScreenshotsDir))
            {
                var compiledFiles = Directory.GetFiles(compiledScreenshotsDir, "*.vmat_c")
                    .Concat(Directory.GetFiles(compiledScreenshotsDir, "*.vtex_c"))
                    .Distinct()
                    .ToList();

                LogToEvent($"Found {compiledFiles.Count} compiled files to process");

                foreach (var filePath in compiledFiles)
                {
                    var fileName = Path.GetFileName(filePath);

                    if (fileName.EndsWith(".vtex_c"))
                    {
                        // For vtex files: mapname_X_png_png_hash.vtex_c -> mapname_X_png.vtex_c
                        // Match pattern: capture everything up to and including first _png, then ignore rest
                        var match = Regex.Match(fileName, @"^(.+_\d+)_png(?:_png)?(?:_[a-f0-9]+)?\.vtex_c$");
                        if (match.Success)
                        {
                            var newName = match.Groups[1].Value + "_png.vtex_c";
                            var newFilePath = Path.Combine(compiledScreenshotsDir, newName);

                            if (filePath != newFilePath)
                            {
                                if (File.Exists(newFilePath))
                                    File.Delete(newFilePath);

                                File.Move(filePath, newFilePath);
                                LogToEvent($"Renamed {fileName} to {newName}");
                            }
                        }
                        else
                        {
                            LogToEvent($"No match for vtex file: {fileName}");
                        }
                    }
                    else if (fileName.EndsWith(".vmat_c"))
                    {
                        // VMAT files: check if they need renaming too
                        var match = Regex.Match(fileName, @"^(.+_\d+)_png\.vmat_c$");
                        if (match.Success)
                        {
                            // Already correct format
                            LogToEvent($"VMAT file already correct: {fileName}");
                        }
                    }
                }
            }

            // Handle compiled SVG file (.vsvg_c)
            if (Directory.Exists(compiledIconsDir))
            {
                var svgCompiledFiles = Directory.GetFiles(compiledIconsDir, $"map_icon_{mapName}_svg_*.vsvg_c");

                foreach (var filePath in svgCompiledFiles)
                {
                    var fileName = Path.GetFileName(filePath);
                    var parts = fileName.Split(new[] { "_svg_" }, StringSplitOptions.None);

                    if (parts.Length > 1)
                    {
                        var newName = parts[0] + "_svg" + fileName[fileName.LastIndexOf('.')..];
                        var newFilePath = Path.Combine(compiledIconsDir, newName);

                        if (File.Exists(newFilePath))
                            File.Delete(newFilePath);

                        File.Move(filePath, newFilePath);
                        LogToEvent($"Renamed {fileName} to {newName}");
                    }
                }
            }

            LogToEvent("Compiled files handling completed");
            return Task.CompletedTask;
        }
    }
}
