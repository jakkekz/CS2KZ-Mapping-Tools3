using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Imaging;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Net.Http;
using System.Threading.Tasks;
using System.Windows.Forms;
using ImageMagick;

#nullable enable

namespace CS2KZMappingTools
{
    public partial class SkyboxConverterForm : Form
    {
        private readonly ThemeManager _themeManager;
        public event Action<string>? LogMessage;

        // UI Controls
        private Button? _selectFilesButton;
        private Button? _resetButton;
        private Button? _convertButton;
        private ComboBox? _addonComboBox;
        private TextBox? _skyboxNameTextBox;
        private CheckBox? _createSkyboxVmatCheckBox;
        private CheckBox? _createMoondomeVmatCheckBox;
        private ProgressBar? _progressBar;

        // Preview Controls
        private PictureBox[]? _facePictureBoxes;
        private Label[]? _faceLabels;
        private Point _mouseDownPoint;
        private System.Windows.Forms.Timer? _dragTimer;
        private PictureBox? _pendingDragPictureBox;

        // Skybox data
        private Dictionary<string, Image>? _faceImages;
        private Dictionary<string, string>? _faceFilePaths; // Store original file paths for full-resolution loading
        private Dictionary<string, int>? _faceRotations;
        private Dictionary<int, string>? _positionToFace; // Maps preview position index to current face name
        private List<string>? _selectedFiles;
        private string[] _faceNames = { "up", "down", "left", "front", "right", "back" };
        private string[] _addonList = Array.Empty<string>();
        private string? _cs2Path;

        // VTF Tools
        private string? _vtfCmdPath;
        private bool _vtfToolsAvailable = false;

        private void FacePictureBox_MouseDown(object? sender, MouseEventArgs e)
        {
            if (sender is PictureBox pictureBox && pictureBox.Image != null)
            {
                _mouseDownPoint = e.Location;
                _pendingDragPictureBox = pictureBox;
                _dragTimer?.Start();
            }
        }

        private void FacePictureBox_DragEnter(object? sender, DragEventArgs e)
        {
            if (e.Data.GetDataPresent(typeof(int)))
            {
                e.Effect = DragDropEffects.Move;
            }
        }

        private void FacePictureBox_DragDrop(object? sender, DragEventArgs e)
        {
            if (sender is PictureBox targetPictureBox &&
                e.Data.GetDataPresent(typeof(int)) &&
                targetPictureBox.Tag is int targetIndex)
            {
                var sourceIndex = (int)e.Data.GetData(typeof(int));

                if (sourceIndex != targetIndex)
                {
                    LogMessage?.Invoke($"DragDrop: Swapping PictureBox {sourceIndex} with PictureBox {targetIndex}");
                    SwapFaces(sourceIndex, targetIndex);
                }
            }
        }

        private void FacePictureBox_MouseEnter(object? sender, EventArgs e)
        {
            if (sender is PictureBox pictureBox && pictureBox.Image != null)
            {
                pictureBox.Cursor = Cursors.Hand;
            }
        }

        private void FacePictureBox_MouseLeave(object? sender, EventArgs e)
        {
            if (sender is PictureBox pictureBox)
            {
                pictureBox.Cursor = Cursors.Default;
            }
        }

        private void FacePictureBox_GiveFeedback(object? sender, GiveFeedbackEventArgs e)
        {
            // Use custom cursor to show dragging
            if (e.Effect == DragDropEffects.Move)
            {
                e.UseDefaultCursors = false;
                Cursor.Current = Cursors.Hand;
            }
            else
            {
                e.UseDefaultCursors = true;
            }
        }

        private void FacePictureBox_MouseUp(object? sender, MouseEventArgs e)
        {
            _dragTimer?.Stop();
            if (_pendingDragPictureBox != null && sender is PictureBox pictureBox && pictureBox.Image != null && pictureBox.Tag is int index)
            {
                var distance = Math.Sqrt(Math.Pow(e.X - _mouseDownPoint.X, 2) + Math.Pow(e.Y - _mouseDownPoint.Y, 2));
                if (distance < 5)
                {
                    LogMessage?.Invoke($"Rotating face at position {index}");
                    var faceName = _positionToFace[index];
                    _faceRotations[faceName] = (_faceRotations[faceName] + 90) % 360;
                    UpdatePreview();
                }
            }
            _pendingDragPictureBox = null;
        }

        private void DragTimer_Tick(object? sender, EventArgs e)
        {
            _dragTimer?.Stop();
            // Don't clear _pendingDragPictureBox here - let MouseUp handle it
            // This allows for clicks that are held longer than the timer interval
        }

        private void FacePictureBox_MouseMove(object? sender, MouseEventArgs e)
        {
            if (_pendingDragPictureBox != null && sender is PictureBox pictureBox && pictureBox == _pendingDragPictureBox && pictureBox.Image != null)
            {
                var distance = Math.Sqrt(Math.Pow(e.X - _mouseDownPoint.X, 2) + Math.Pow(e.Y - _mouseDownPoint.Y, 2));
                if (distance > 5)
                {
                    _dragTimer?.Stop();
                    LogMessage?.Invoke($"Starting drag from position {pictureBox.Tag}");
                    pictureBox.DoDragDrop(pictureBox.Tag, DragDropEffects.Move);
                    _pendingDragPictureBox = null;
                }
            }
        }

        private Image RotateImage(Image image, int degrees)
        {
            if (degrees == 0) return (Image)image.Clone();

            // Create a new bitmap with the rotated image
            using (var bitmap = new Bitmap(image))
            {
                bitmap.RotateFlip((RotateFlipType)(degrees / 90));
                return (Image)bitmap.Clone();
            }
        }

        public SkyboxConverterForm(ThemeManager themeManager)
        {
            _themeManager = themeManager;
            _dragTimer = new System.Windows.Forms.Timer();
            _dragTimer.Interval = 200; // 200ms delay for click vs drag
            _dragTimer.Tick += DragTimer_Tick;
            InitializeComponent();
            InitializeSkybox();
            ApplyTheme();
        }

        private void InitializeComponent()
        {
            this.Text = "Skybox Converter";
            this.Size = new Size(1000, 650); // Larger size to accommodate bigger preview images and instructions
            this.StartPosition = FormStartPosition.CenterParent;
            this.FormBorderStyle = FormBorderStyle.FixedDialog;
            this.MaximizeBox = false;
            this.MinimizeBox = false;

            // Initialize preview controls first
            InitializePreviewControls();

            // Add instruction label above preview (split into multiple lines, positioned to the left)
            var instructionLabel = new Label
            {
                Text = "- Drag images to rearrange\n- Click images to rotate\n- Known supported formats:\n   VTF, PNG, JPG, TGA, EXR",
                Location = new Point(20, 110),
                Size = new Size(170, 75),
                TextAlign = ContentAlignment.TopLeft,
                ForeColor = Color.Gray
            };
            this.Controls.Add(instructionLabel);

            // Select Files Button
            _selectFilesButton = new Button
            {
                Text = "Select Skybox Files (6 faces)",
                Location = new Point(20, 20),
                Size = new Size(180, 35),
                FlatStyle = FlatStyle.Flat
            };
            _selectFilesButton.Click += SelectFilesButton_Click;

            // Reset Button
            _resetButton = new Button
            {
                Text = "Reset",
                Location = new Point(20, 550),
                Size = new Size(80, 35),
                FlatStyle = FlatStyle.Flat,
                Enabled = false
            };
            _resetButton.Click += ResetButton_Click;

            // Skybox Name TextBox
            var nameLabel = new Label
            {
                Text = "Output Name:",
                Location = new Point(500, 558),
                Size = new Size(90, 20)
            };

            _skyboxNameTextBox = new TextBox
            {
                Location = new Point(595, 555),
                Size = new Size(230, 25),
                Text = $"skybox_{DateTime.Now:yyyyMMdd_HHmmss}"
            };

            // Addon ComboBox
            var addonLabel = new Label
            {
                Text = "Addon:",
                Location = new Point(220, 25),
                Size = new Size(50, 20)
            };

            _addonComboBox = new ComboBox
            {
                Location = new Point(270, 20),
                Size = new Size(200, 25),
                DropDownStyle = ComboBoxStyle.DropDownList
            };

            // Checkboxes
            _createSkyboxVmatCheckBox = new CheckBox
            {
                Text = "Create Skybox .vmat",
                Location = new Point(500, 20),
                Size = new Size(150, 20),
                Checked = true
            };

            _createMoondomeVmatCheckBox = new CheckBox
            {
                Text = "Create Moondome .vmat",
                Location = new Point(500, 45),
                Size = new Size(150, 20),
                Checked = false
            };

            // Convert Button
            _convertButton = new Button
            {
                Text = "Convert to Skybox",
                Location = new Point(840, 550),
                Size = new Size(120, 35),
                FlatStyle = FlatStyle.Flat,
                Enabled = false
            };
            _convertButton.Click += ConvertButton_Click;

            // Progress Bar
            _progressBar = new ProgressBar
            {
                Location = new Point(20, 670),
                Size = new Size(900, 25),
                Style = ProgressBarStyle.Continuous,
                Visible = false
            };

            this.Controls.AddRange(new Control[] {
                _selectFilesButton, _resetButton, nameLabel, _skyboxNameTextBox, addonLabel, _addonComboBox,
                _createSkyboxVmatCheckBox, _createMoondomeVmatCheckBox,
                _convertButton, _progressBar
            });

            // Add preview controls to the form
            if (_facePictureBoxes != null && _faceLabels != null)
            {
                this.Controls.AddRange(_facePictureBoxes);
                this.Controls.AddRange(_faceLabels);
            }
        }

        private void InitializePreviewControls()
        {
            _facePictureBoxes = new PictureBox[6];
            _faceLabels = new Label[6];

            // Layout positions: arranged with up touching front, down touching front, and left/front/right/back touching horizontally
            // Using consistent spacing - each box is 150x150 pixels, positioned to touch perfectly with no gaps
            int boxSize = 150;
            int startX = 100;
            int middleY = 250;
            
            var positions = new Point[]
            {
                new Point(startX + boxSize, middleY - boxSize),     // up (directly above front)
                new Point(startX + boxSize, middleY + boxSize),     // down (directly below front)
                new Point(startX, middleY),                         // left
                new Point(startX + boxSize, middleY),               // front (center)
                new Point(startX + boxSize * 2, middleY),           // right
                new Point(startX + boxSize * 3, middleY),           // back
            };

            for (int i = 0; i < 6; i++)
            {
                // PictureBox for face image - larger size
                _facePictureBoxes[i] = new PictureBox
                {
                    Location = positions[i],
                    Size = new Size(150, 150), // Larger images for better preview
                    BorderStyle = BorderStyle.None,
                    BackColor = Color.Transparent,
                    SizeMode = PictureBoxSizeMode.Zoom, // Zoom to fit without distortion
                    AllowDrop = true,
                    Tag = i
                };
                _facePictureBoxes[i].MouseDown += FacePictureBox_MouseDown;
                _facePictureBoxes[i].MouseMove += FacePictureBox_MouseMove;
                _facePictureBoxes[i].MouseUp += FacePictureBox_MouseUp;
                _facePictureBoxes[i].DragEnter += FacePictureBox_DragEnter;
                _facePictureBoxes[i].DragDrop += FacePictureBox_DragDrop;

                // Face label - positioned inside image
                _faceLabels[i] = new Label
                {
                    Location = new Point(positions[i].X + 2, positions[i].Y + 2), // Inside image
                    AutoSize = true, // Auto-size to fit text width
                    Text = _faceNames[i],
                    TextAlign = ContentAlignment.MiddleCenter,
                    ForeColor = Color.Black, // Black text for visibility on white background
                    BackColor = Color.White, // White background instead of purple/semi-transparent
                    Tag = i
                };
            }
        }

        private void ApplyTheme()
        {
            var theme = _themeManager.GetCurrentTheme();
            this.BackColor = theme.WindowBackground;
            this.ForeColor = theme.Text;

            foreach (Control control in this.Controls)
            {
                ApplyThemeToControl(control);
            }

            // Apply theme to preview controls
            if (_facePictureBoxes != null)
            {
                foreach (var pictureBox in _facePictureBoxes)
                {
                    // Show grey squares for empty picture boxes to indicate available slots
                    if (pictureBox.Image == null)
                    {
                        pictureBox.BackColor = Color.Gray;
                    }
                    else
                    {
                        pictureBox.BackColor = Color.Transparent;
                        pictureBox.Cursor = Cursors.Hand; // Indicate grabbable when has image
                    }
                }
            }

            if (_faceLabels != null)
            {
                foreach (var label in _faceLabels)
                {
                    // Don't apply theme to face labels - they need white background with black text for visibility
                    if (label.BackColor != Color.White)
                    {
                        label.ForeColor = theme.Text;
                    }
                }
            }
        }

        private void ApplyThemeToControl(Control control)
        {
            var theme = _themeManager.GetCurrentTheme();

            if (control is Button button)
            {
                button.BackColor = theme.ButtonBackground;
                button.ForeColor = theme.Text;
                button.FlatAppearance.BorderColor = theme.Border;
            }
            else if (control is TextBox textBox)
            {
                textBox.BackColor = theme.ButtonBackground;
                textBox.ForeColor = theme.Text;
            }
            else if (control is ListBox listBox)
            {
                listBox.BackColor = theme.ButtonBackground;
                listBox.ForeColor = theme.Text;
            }
            else if (control is Label label)
            {
                label.ForeColor = theme.Text;
            }
            else if (control is CheckBox checkBox)
            {
                checkBox.ForeColor = theme.Text;
            }
            else if (control is ComboBox comboBox)
            {
                comboBox.BackColor = theme.ButtonBackground;
                comboBox.ForeColor = theme.Text;
            }
        }

        private async void InitializeSkybox()
        {
            _faceImages = new Dictionary<string, Image>();
            _faceFilePaths = new Dictionary<string, string>();
            _faceRotations = new Dictionary<string, int>();
            _positionToFace = new Dictionary<int, string>();
            _selectedFiles = new List<string>();

            // Initialize position to face mapping (initially matches _faceNames indices)
            for (int i = 0; i < _faceNames.Length; i++)
            {
                _positionToFace[i] = _faceNames[i];
            }

            foreach (var face in _faceNames)
            {
                _faceRotations[face] = 0;
            }

            Debug.WriteLine("Checking for VTF conversion tools...");
            await Task.Run(() => FindOrDownloadVtfTools());
            Debug.WriteLine("Auto-detecting CS2 installation...");
            await Task.Run(() => AutoDetectCS2());

            // Initialize preview with grey squares
            UpdatePreview();

            UpdateUI();
        }

        private void FindOrDownloadVtfTools()
        {
            try
            {
                // Check 1: .CS2KZ-mapping-tools/vtf folder in Temp (preferred - shared location)
                string tempDir = Path.GetTempPath();
                string toolsDir = Path.Combine(tempDir, ".CS2KZ-mapping-tools", "vtf");
                string vtfCmdPath = Path.Combine(toolsDir, "VTFCmd.exe");
                string vtfLibPath = Path.Combine(toolsDir, "VTFLib.dll");

                if (File.Exists(vtfCmdPath) && File.Exists(vtfLibPath))
                {
                    _vtfCmdPath = vtfCmdPath;
                    _vtfToolsAvailable = true;
                    LogMessage?.Invoke($"[Skybox] Using VTF tools from: {_vtfCmdPath}");
                    return;
                }

                // Check 2: Bundled VTF tools (fallback)
                string basePath = ResourceExtractor.ExtractResources();
                string bundledVtfCmd = Path.Combine(basePath, "vtf", "VTFCmd.exe");

                if (File.Exists(bundledVtfCmd))
                {
                    string bundledVtfLib = Path.Combine(basePath, "vtf", "VTFLib.dll");
                    if (File.Exists(bundledVtfLib))
                    {
                        _vtfCmdPath = bundledVtfCmd;
                        _vtfToolsAvailable = true;
                        LogMessage?.Invoke($"[Skybox] Using bundled VTF tools from: {_vtfCmdPath}");
                        return;
                    }
                }

                // Download VTF tools if not found anywhere
                Directory.CreateDirectory(toolsDir);

                LogMessage?.Invoke("[Skybox] VTF tools not found. Downloading from GitHub...");
                LogMessage?.Invoke("[Skybox] This is a one-time download (~2 MB)...");

                string downloadUrl = "https://nemstools.github.io/files/vtflib132-bin.zip";
                LogMessage?.Invoke($"[Skybox] Downloading VTFLib binaries from {downloadUrl}...");

                using (var httpClient = new HttpClient())
                {
                    httpClient.Timeout = TimeSpan.FromSeconds(30);
                    var downloadData = httpClient.GetByteArrayAsync(downloadUrl).Result;

                    // Extract required files from the zip
                    using (var memoryStream = new MemoryStream(downloadData))
                    using (var zipArchive = new ZipArchive(memoryStream))
                    {
                        var requiredFiles = new Dictionary<string, string>
                        {
                            ["VTFCmd.exe"] = vtfCmdPath,
                            ["VTFLib.dll"] = vtfLibPath,
                            ["DevIL.dll"] = Path.Combine(toolsDir, "DevIL.dll"),
                            ["ILU.dll"] = Path.Combine(toolsDir, "ILU.dll"),
                            ["ILUT.dll"] = Path.Combine(toolsDir, "ILUT.dll")
                        };

                        var foundFiles = new HashSet<string>();

                        foreach (var entry in zipArchive.Entries)
                        {
                            foreach (var requiredFile in requiredFiles)
                            {
                                if (entry.FullName.Contains(requiredFile.Key) && !foundFiles.Contains(requiredFile.Key))
                                {
                                    // Prefer x64 version
                                    if (entry.FullName.Contains("x64") || !foundFiles.Contains(requiredFile.Key))
                                    {
                                        using (var entryStream = entry.Open())
                                        using (var fileStream = File.Create(requiredFile.Value))
                                        {
                                            entryStream.CopyTo(fileStream);
                                        }
                                        foundFiles.Add(requiredFile.Key);
                                        LogMessage?.Invoke($"[Skybox] Extracted {requiredFile.Key}");
                                        break;
                                    }
                                }
                            }
                        }

                        if (foundFiles.Contains("VTFCmd.exe") && foundFiles.Contains("VTFLib.dll"))
                        {
                            _vtfCmdPath = vtfCmdPath;
                            _vtfToolsAvailable = true;
                            LogMessage?.Invoke($"[Skybox] VTF tools installed to: {toolsDir}");
                        }
                        else
                        {
                            LogMessage?.Invoke("[Skybox] Failed to extract required VTF tools from archive");
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                LogMessage?.Invoke($"[Skybox] Error initializing VTF tools: {ex.Message}");
            }
        }

        private void AutoDetectCS2()
        {
            try
            {
                // Try to find CS2 path from registry
                var cs2Path = GetCs2Path();
                if (!string.IsNullOrEmpty(cs2Path) && Directory.Exists(cs2Path))
                {
                    _cs2Path = cs2Path;
                    LogMessage?.Invoke($"[Skybox] Auto-detected CS2: {_cs2Path}");

                    // Find addons
                    var addonsPath = Path.Combine(_cs2Path, "content", "csgo_addons");
                    if (Directory.Exists(addonsPath))
                    {
                        _addonList = Directory.GetDirectories(addonsPath)
                            .Select(d => Path.GetFileName(d))
                            .Where(name => !string.IsNullOrEmpty(name) && 
                                          !name.Equals("addon_template", StringComparison.OrdinalIgnoreCase) &&
                                          !name.Equals("addontemplate", StringComparison.OrdinalIgnoreCase))
                            .ToArray();

                        if (_addonList.Length > 0)
                        {
                            LogMessage?.Invoke($"[Skybox] Found {_addonList.Length} addons");
                            this.Invoke(new Action(() =>
                            {
                                _addonComboBox.Items.Clear();
                                _addonComboBox.Items.AddRange(_addonList);
                                if (_addonList.Length > 0)
                                {
                                    _addonComboBox.SelectedIndex = 0;
                                }
                            }));
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                LogMessage?.Invoke($"[Skybox] Error detecting CS2: {ex.Message}");
            }
        }

        private string GetCs2Path()
        {
            try
            {
                // Try Steam registry
                var steamKey = Microsoft.Win32.Registry.LocalMachine.OpenSubKey(@"SOFTWARE\WOW6432Node\Valve\Steam");
                if (steamKey != null)
                {
                    var steamPath = steamKey.GetValue("InstallPath") as string;
                    if (!string.IsNullOrEmpty(steamPath))
                    {
                        var libraryFolders = Path.Combine(steamPath, "steamapps", "libraryfolders.vdf");
                        if (File.Exists(libraryFolders))
                        {
                            var content = File.ReadAllText(libraryFolders);
                            var lines = content.Split('\n');

                            foreach (var line in lines)
                            {
                                if (line.Contains("730")) // CS2 AppID
                                {
                                    // Find the path in this library
                                    var pathLine = lines.SkipWhile(l => !l.Contains(line.Trim())).Skip(1)
                                        .FirstOrDefault(l => l.Contains("path"));
                                    if (pathLine != null)
                                    {
                                        var match = System.Text.RegularExpressions.Regex.Match(pathLine, "\"path\"\\s+\"([^\"]+)\"");
                                        if (match.Success)
                                        {
                                            var libraryPath = match.Groups[1].Value.Replace("\\\\", "\\");
                                            var cs2Path = Path.Combine(libraryPath, "steamapps", "common", "Counter-Strike Global Offensive");
                                            if (Directory.Exists(cs2Path))
                                            {
                                                return cs2Path;
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
            catch { }

            return null;
        }

        private void UpdateUI()
        {
            if (this.InvokeRequired)
            {
                this.Invoke(new Action(UpdateUI));
                return;
            }

            if (_vtfToolsAvailable)
            {
                _selectFilesButton.Enabled = true;
            }
            else
            {
                _selectFilesButton.Enabled = false;
            }

            _resetButton.Enabled = _faceImages.Count == 6;
            _convertButton.Enabled = _vtfToolsAvailable && _faceImages.Count == 6 && _addonList.Length > 0;
        }

        private void Log(string message)
        {
            LogMessage?.Invoke($"[{DateTime.Now:HH:mm:ss}] {message}");
        }

        private void SelectFilesButton_Click(object? sender, EventArgs e)
        {
            using (var openFileDialog = new OpenFileDialog())
            {
                openFileDialog.Title = "Select all 6 skybox face images";
                openFileDialog.Filter = "Image files (*.vtf;*.png;*.jpg;*.jpeg;*.tga;*.exr)|*.vtf;*.png;*.jpg;*.jpeg;*.tga;*.exr|All files (*.*)|*.*";
                openFileDialog.Multiselect = true;

                if (openFileDialog.ShowDialog() == DialogResult.OK)
                {
                    _selectedFiles = openFileDialog.FileNames.ToList();
                    LoadAndArrangeFaces();
                }
            }
        }

        private void ResetButton_Click(object? sender, EventArgs e)
        {
            // Reset all rotations to 0
            foreach (var face in _faceNames)
            {
                _faceRotations[face] = 0;
            }

            // Reset position mappings to default
            for (int i = 0; i < _faceNames.Length; i++)
            {
                _positionToFace[i] = _faceNames[i];
            }

            // Re-arrange faces to default positions if we have files loaded
            if (_selectedFiles != null && _selectedFiles.Count == 6)
            {
                LoadAndArrangeFaces();
            }

            UpdatePreview();
        }

        private void LoadAndArrangeFaces()
        {
            if (_selectedFiles == null || _selectedFiles.Count != 6) return;

            // Clear existing images
            foreach (var kvp in _faceImages)
            {
                kvp.Value?.Dispose();
            }
            _faceImages.Clear();
            _faceFilePaths.Clear();

            // Auto-detect faces based on filename patterns
            var facePatterns = new Dictionary<string, string[]>
            {
                ["up"] = new[] { "up", "top", "pz" },
                ["down"] = new[] { "down", "dn", "nz" },
                ["left"] = new[] { "left", "lf", "nx" },
                ["right"] = new[] { "right", "rt", "px" },
                ["front"] = new[] { "front", "ft", "ny" },
                ["back"] = new[] { "back", "bk", "py" }
            };

            var assignedFaces = new Dictionary<string, string>();

            foreach (var filePath in _selectedFiles)
            {
                var fileName = Path.GetFileNameWithoutExtension(filePath).ToLower();
                bool assigned = false;

                foreach (var facePattern in facePatterns)
                {
                    foreach (var pattern in facePattern.Value)
                    {
                        if (fileName.Contains(pattern))
                        {
                            if (!assignedFaces.ContainsKey(facePattern.Key))
                            {
                                assignedFaces[facePattern.Key] = filePath;
                                assigned = true;
                                break;
                            }
                        }
                    }
                    if (assigned) break;
                }

                // If not auto-assigned, assign to first available slot
                if (!assigned)
                {
                    foreach (var face in _faceNames)
                    {
                        if (!assignedFaces.ContainsKey(face))
                        {
                            assignedFaces[face] = filePath;
                            break;
                        }
                    }
                }
            }

            // Load images
            foreach (var faceAssignment in assignedFaces)
            {
                try
                {
                    var image = LoadImage(faceAssignment.Value, forPreview: true);
                    if (image != null)
                    {
                        _faceImages[faceAssignment.Key] = image;
                        _faceFilePaths[faceAssignment.Key] = faceAssignment.Value; // Store original file path
                    }
                }
                catch (Exception ex)
                {
                    LogMessage?.Invoke($"[Skybox] Error loading {faceAssignment.Key}: {ex.Message}");
                }
            }

            UpdatePreview();
            UpdateUI();
        }

        private Image LoadImage(string filePath, bool forPreview = true)
        {
            var extension = Path.GetExtension(filePath).ToLower();

            Image image = null;

            if (extension == ".exr" || extension == ".tga")
            {
                // Convert EXR/TGA to PNG for preview using ImageMagick
                var convertedPng = ConvertImageMagickToPng(filePath);
                if (convertedPng != null && File.Exists(convertedPng))
                {
                    try
                    {
                        // Load image with retry logic to handle file locking
                        image = LoadImageFromFile(convertedPng, maxRetries: 10, delayMs: 200);
                        // Clean up the temp file after loading
                        try { File.Delete(convertedPng); } catch { /* Ignore delete errors */ }
                    }
                    catch (Exception ex)
                    {
                        Log($"[{extension.ToUpper()}] Error loading converted preview: {ex.Message}");
                        // Fallback to placeholder
                        image = new Bitmap(512, 512);
                        using (var graphics = Graphics.FromImage(image))
                        {
                            graphics.Clear(Color.Gray);
                            using (var font = new Font("Arial", 24))
                            using (var brush = new SolidBrush(Color.White))
                            {
                                graphics.DrawString($"{extension.ToUpper()}\nConversion Failed", font, brush, new PointF(180, 220));
                            }
                        }
                    }
                }
                else
                {
                    // Create a placeholder image when conversion fails
                    image = new Bitmap(512, 512);
                    using (var graphics = Graphics.FromImage(image))
                    {
                        graphics.Clear(Color.Gray);
                        using (var font = new Font("Arial", 24))
                        using (var brush = new SolidBrush(Color.White))
                        {
                            graphics.DrawString($"{extension.ToUpper()}\nConversion Failed", font, brush, new PointF(180, 220));
                        }
                    }
                }
            }
            else if (extension == ".vtf")
            {
                // Convert VTF to PNG for preview
                var convertedPng = ConvertVtfToPng(filePath);
                if (convertedPng != null && File.Exists(convertedPng))
                {
                    try
                    {
                        // Load image with retry logic to handle file locking
                        image = LoadImageFromFile(convertedPng, maxRetries: 10, delayMs: 200);
                        // Clean up the temp file after loading
                        try { File.Delete(convertedPng); } catch { /* Ignore delete errors */ }
                    }
                    catch (Exception ex)
                    {
                        Log($"[VTF] Error loading converted VTF preview: {ex.Message}");
                        // Fallback to placeholder
                        image = new Bitmap(512, 512);
                        using (var graphics = Graphics.FromImage(image))
                        {
                            graphics.Clear(Color.Gray);
                            using (var font = new Font("Arial", 24))
                            using (var brush = new SolidBrush(Color.White))
                            {
                                graphics.DrawString("VTF\nConversion Failed", font, brush, new PointF(180, 220));
                            }
                        }
                    }
                }
                else
                {
                    // Create a placeholder image for VTF files when conversion fails
                    image = new Bitmap(512, 512);
                    using (var graphics = Graphics.FromImage(image))
                    {
                        graphics.Clear(Color.Gray);
                        using (var font = new Font("Arial", 24))
                        using (var brush = new SolidBrush(Color.White))
                        {
                            graphics.DrawString("VTF\nConversion Failed", font, brush, new PointF(180, 220));
                        }
                    }
                }
            }
            else
            {
                // Use helper to avoid file locking issues
                try
                {
                    image = LoadImageFromFile(filePath);
                }
                catch (Exception ex)
                {
                    Log($"[Image] Error loading {Path.GetFileName(filePath)}: {ex.Message}");
                    // Create placeholder
                    image = new Bitmap(512, 512);
                    using (var graphics = Graphics.FromImage(image))
                    {
                        graphics.Clear(Color.Gray);
                        using (var font = new Font("Arial", 24))
                        using (var brush = new SolidBrush(Color.White))
                        {
                            graphics.DrawString("Load Failed", font, brush, new PointF(180, 220));
                        }
                    }
                }
            }

            if (image != null && forPreview)
            {
                // Always check image size and resize if too large to prevent out of memory errors
                const int maxPreviewSize = 512;
                if (image.Width > maxPreviewSize || image.Height > maxPreviewSize)
                {
                    var resizedImage = ResizeImage(image, maxPreviewSize, maxPreviewSize);
                    image.Dispose(); // Dispose the original large image
                    return resizedImage;
                }
            }

            return image;
        }

        private Image LoadImageFromFile(string path, int maxRetries = 5, int delayMs = 200)
        {
            Exception lastException = null;
            
            for (int i = 0; i < maxRetries; i++)
            {
                try
                {
                    // Load image into memory without locking the file
                    using (var stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite))
                    {
                        var image = Image.FromStream(stream);
                        // Create a copy in memory so we can close the stream
                        var memoryImage = new Bitmap(image);
                        image.Dispose();
                        return memoryImage;
                    }
                }
                catch (Exception ex)
                {
                    lastException = ex;
                    if (i < maxRetries - 1)
                    {
                        System.Threading.Thread.Sleep(delayMs);
                    }
                }
            }
            
            throw lastException ?? new IOException("Failed to load image");
        }

        private Image ResizeImage(Image image, int maxWidth, int maxHeight)
        {
            var ratioX = (double)maxWidth / image.Width;
            var ratioY = (double)maxHeight / image.Height;
            var ratio = Math.Min(ratioX, ratioY);

            var newWidth = (int)(image.Width * ratio);
            var newHeight = (int)(image.Height * ratio);

            var newImage = new Bitmap(newWidth, newHeight);

            using (var graphics = Graphics.FromImage(newImage))
            {
                graphics.CompositingQuality = System.Drawing.Drawing2D.CompositingQuality.HighQuality;
                graphics.InterpolationMode = System.Drawing.Drawing2D.InterpolationMode.HighQualityBicubic;
                graphics.SmoothingMode = System.Drawing.Drawing2D.SmoothingMode.HighQuality;
                graphics.DrawImage(image, 0, 0, newWidth, newHeight);
            }

            return newImage;
        }

        private string ConvertVtfToPng(string vtfPath)
        {
            if (string.IsNullOrEmpty(_vtfCmdPath) || !File.Exists(_vtfCmdPath))
            {
                Log($"[VTF] ERROR: VTFCmd.exe not found at {_vtfCmdPath}");
                return null;
            }

            try
            {
                var tempDir = Path.Combine(Path.GetTempPath(), ".CS2KZ-mapping-tools");
                Directory.CreateDirectory(tempDir); // Ensure the directory exists
                var outputPng = Path.Combine(tempDir, Path.GetFileNameWithoutExtension(vtfPath) + ".png");

                // VTFCmd.exe command for VTF to PNG conversion (no resize parameters to avoid parsing issues)
                var startInfo = new ProcessStartInfo
                {
                    FileName = _vtfCmdPath,
                    Arguments = $"-file \"{vtfPath}\" -output \"{tempDir}\" -exportformat png",
                    WorkingDirectory = Path.GetDirectoryName(_vtfCmdPath),
                    UseShellExecute = false,
                    CreateNoWindow = true,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true
                };

                using (var process = Process.Start(startInfo))
                {
                    if (process != null)
                    {
                        var stdout = process.StandardOutput.ReadToEnd();
                        var stderr = process.StandardError.ReadToEnd();
                        process.WaitForExit();
                        
                        // Give VTFCmd.exe time to fully release file handles
                        System.Threading.Thread.Sleep(100);
                        
                        if (process.ExitCode == 0 && File.Exists(outputPng))
                        {
                            Log($"[VTF] ✓ Converted {Path.GetFileName(vtfPath)} successfully");
                            return outputPng;
                        }
                        else
                        {
                            // Only log detailed error information on actual failure
                            Log($"[VTF] ✗ Conversion failed - Exit code: {process.ExitCode}");
                            if (!string.IsNullOrWhiteSpace(stdout)) Log($"[VTF] Output: {stdout}");
                            if (!string.IsNullOrWhiteSpace(stderr)) Log($"[VTF] Error: {stderr}");
                        }
                    }
                    else
                    {
                        Log("[VTF] ERROR: Failed to start VTFCmd process");
                    }
                }
            }
            catch (Exception ex)
            {
                Log($"[VTF] ERROR: Exception during conversion: {ex.Message}");
            }

            return null;
        }

        private string ConvertImageMagickToPng(string imagePath)
        {
            try
            {
                var tempDir = Path.Combine(Path.GetTempPath(), ".CS2KZ-mapping-tools");
                Directory.CreateDirectory(tempDir);
                var outputPng = Path.Combine(tempDir, Path.GetFileNameWithoutExtension(imagePath) + ".png");

                // Use ImageMagick to convert image to PNG
                using (var image = new MagickImage(imagePath))
                {
                    // Set format to PNG
                    image.Format = MagickFormat.Png32;
                    
                    // Ensure proper color depth
                    image.Depth = 8;
                    
                    // Write to PNG
                    image.Write(outputPng);
                }

                if (File.Exists(outputPng))
                {
                    Log($"[ImageMagick] ✓ Converted {Path.GetFileName(imagePath)} successfully");
                    return outputPng;
                }
                else
                {
                    Log($"[ImageMagick] ✗ Conversion failed - output file not created");
                }
            }
            catch (Exception ex)
            {
                Log($"[ImageMagick] ERROR: Exception during conversion: {ex.Message}");
            }

            return null;
        }

        private void UpdatePreview()
        {
            if (_facePictureBoxes == null) return;

            for (int i = 0; i < _faceNames.Length; i++)
            {
                var faceName = _positionToFace[i]; // Use current face in this position
                var pictureBox = _facePictureBoxes[i];

                if (_faceImages.TryGetValue(faceName, out var image))
                {
                    // Apply rotation
                    var rotatedImage = RotateImage(image, _faceRotations[faceName]);
                    pictureBox.Image = rotatedImage;
                    pictureBox.BackColor = Color.Transparent;
                    pictureBox.Cursor = Cursors.Hand; // Grabbable cursor for images
                }
                else
                {
                    pictureBox.Image = null;
                    pictureBox.BackColor = Color.Gray; // Grey placeholder
                    pictureBox.Cursor = Cursors.Default; // Default cursor for empty slots
                }
            }
        }

        private void SwapFaces(int index1, int index2)
        {
            // Swap which face is in each position
            var face1 = _positionToFace[index1];
            var face2 = _positionToFace[index2];
            _positionToFace[index1] = face2;
            _positionToFace[index2] = face1;

            UpdatePreview();
        }

        private void RotateFace(int positionIndex)
        {
            // Get the face name at this position
            var faceName = _positionToFace[positionIndex];
            
            // Rotate 90 degrees clockwise
            _faceRotations[faceName] = (_faceRotations[faceName] + 90) % 360;
            
            UpdatePreview();
        }

        private async void ConvertButton_Click(object? sender, EventArgs e)
        {
            if (!_vtfToolsAvailable || _faceImages == null || _faceImages.Count != 6 ||
                _addonComboBox == null || _addonComboBox.SelectedIndex < 0)
                return;

            _convertButton.Enabled = false;
            _progressBar.Visible = true;
            _progressBar.Value = 0;

            try
            {
                var selectedAddon = _addonComboBox.SelectedItem as string;
                var outputDir = GetAddonOutputPath(selectedAddon);

                if (string.IsNullOrEmpty(outputDir))
                {
                    MessageBox.Show("Could not determine output directory", "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
                    return;
                }

                Directory.CreateDirectory(outputDir);

                // Convert any VTF files to PNG first
                var tempPngFiles = new List<string>();
                var convertedImages = new Dictionary<string, Image>();

                _progressBar.Value = 10;

                foreach (var face in _faceNames)
                {
                    if (_faceImages.TryGetValue(face, out var image))
                    {
                        // Check if this came from a VTF or EXR file
                        var originalFile = _selectedFiles.FirstOrDefault(f => 
                            Path.GetFileNameWithoutExtension(f).ToLower().Contains(face) ||
                            f.ToLower().Contains(face));

                        var extension = originalFile != null ? Path.GetExtension(originalFile).ToLower() : "";

                        if (extension == ".vtf")
                        {
                            // Convert VTF to PNG
                            var (success, pngPath) = await ConvertVtfToPngAsync(originalFile, Path.GetTempPath());
                            if (success)
                            {
                                tempPngFiles.Add(pngPath);
                                // Load the converted PNG with retry logic
                                var pngImage = LoadImageFromFile(pngPath);
                                convertedImages[face] = pngImage;
                            }
                            else
                            {
                                LogMessage?.Invoke($"[Skybox] Failed to convert VTF for {face}: {pngPath}");
                                convertedImages[face] = image; // Use original if conversion failed
                            }
                        }
                        else if (extension == ".exr" || extension == ".tga")
                        {
                            // Convert EXR/TGA to PNG
                            var (success, pngPath) = await ConvertImageMagickToPngAsync(originalFile, Path.GetTempPath());
                            if (success)
                            {
                                tempPngFiles.Add(pngPath);
                                // Load the converted PNG with retry logic
                                var pngImage = LoadImageFromFile(pngPath);
                                convertedImages[face] = pngImage;
                            }
                            else
                            {
                                LogMessage?.Invoke($"[Skybox] Failed to convert {extension.ToUpper()} for {face}: {pngPath}");
                                convertedImages[face] = image; // Use original if conversion failed
                            }
                        }
                        else
                        {
                            // Load full-resolution image from original file path
                            if (_faceFilePaths.TryGetValue(face, out var filePath))
                            {
                                try
                                {
                                    var fullResImage = LoadImage(filePath, forPreview: false); // Load at full resolution
                                    convertedImages[face] = fullResImage;
                                }
                                catch (Exception ex)
                                {
                                    LogMessage?.Invoke($"[Skybox] Failed to load full-resolution image for {face}: {ex.Message}");
                                    convertedImages[face] = image; // Fallback to preview image
                                }
                            }
                            else
                            {
                                convertedImages[face] = image; // Fallback to preview image
                            }
                        }
                    }
                }

                _progressBar.Value = 30;

                // Temporarily replace face images with converted ones for stitching
                var originalImages = new Dictionary<string, Image>(_faceImages);
                foreach (var kvp in convertedImages)
                {
                    _faceImages[kvp.Key] = kvp.Value;
                }

                // Stitch the skybox
                var stitchedImage = StitchSkybox();
                if (stitchedImage == null)
                {
                    MessageBox.Show("Failed to stitch skybox", "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
                    return;
                }

                _progressBar.Value = 60;

                // Restore original images
                _faceImages = originalImages;

                // Always save the stitched image as PNG
                var skyboxName = string.IsNullOrWhiteSpace(_skyboxNameTextBox?.Text) 
                    ? $"skybox_{DateTime.Now:yyyyMMdd_HHmmss}" 
                    : _skyboxNameTextBox.Text.Trim();
                var outputPngPath = Path.Combine(outputDir, $"{skyboxName}.png");
                stitchedImage.Save(outputPngPath, ImageFormat.Png);

                _progressBar.Value = 80;

                // Create VMAT files
                if (_createSkyboxVmatCheckBox.Checked)
                {
                    CreateSkyboxVmat(outputDir, skyboxName);
                }

                if (_createMoondomeVmatCheckBox.Checked)
                {
                    CreateMoondomeVmat(outputDir, skyboxName);
                }

                _progressBar.Value = 90;

                // Clean up temporary PNG files
                foreach (var tempFile in tempPngFiles)
                {
                    try
                    {
                        if (File.Exists(tempFile))
                        {
                            File.Delete(tempFile);
                        }
                    }
                    catch (Exception ex)
                    {
                        LogMessage?.Invoke($"[Skybox] Warning: Could not delete temp file {tempFile}: {ex.Message}");
                    }
                }

                _progressBar.Value = 100;

                MessageBox.Show($"Skybox conversion completed!\n\nOutput: {outputPngPath}",
                    "Success", MessageBoxButtons.OK, MessageBoxIcon.Information);

            }
            catch (Exception ex)
            {
                MessageBox.Show($"Conversion failed: {ex.Message}", "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
                LogMessage?.Invoke($"[Skybox] Conversion error: {ex.Message}");
            }
            finally
            {
                _progressBar.Visible = false;
                _convertButton.Enabled = true;
            }
        }

        private string GetAddonOutputPath(string addonName)
        {
            if (string.IsNullOrEmpty(_cs2Path) || string.IsNullOrEmpty(addonName))
                return null;

            return Path.Combine(_cs2Path, "content", "csgo_addons", addonName, "materials", "skybox");
        }

        private Bitmap StitchSkybox()
        {
            if (_faceImages == null || _faceImages.Count != 6) return null;

            try
            {
                // Get the size of the first face to determine dimensions
                var firstFace = _faceImages.First().Value;
                var faceSize = Math.Min(firstFace.Width, firstFace.Height);

                // Create 4x3 canvas (CS2 skybox format)
                var canvasWidth = faceSize * 4;
                var canvasHeight = faceSize * 3;

                var canvas = new Bitmap(canvasWidth, canvasHeight, PixelFormat.Format32bppArgb);

                using (var graphics = Graphics.FromImage(canvas))
                {
                    // Set pixel-perfect rendering settings (no anti-aliasing or interpolation)
                    graphics.InterpolationMode = System.Drawing.Drawing2D.InterpolationMode.NearestNeighbor;
                    graphics.PixelOffsetMode = System.Drawing.Drawing2D.PixelOffsetMode.Half;
                    graphics.CompositingMode = System.Drawing.Drawing2D.CompositingMode.SourceCopy;
                    graphics.CompositingQuality = System.Drawing.Drawing2D.CompositingQuality.HighSpeed;
                    
                    graphics.Clear(Color.Transparent);

                    // Define positions for each face in the 4x3 layout
                    var positions = new Dictionary<string, Point>
                    {
                        ["up"] = new Point(faceSize, 0),
                        ["left"] = new Point(0, faceSize),
                        ["front"] = new Point(faceSize, faceSize),
                        ["right"] = new Point(faceSize * 2, faceSize),
                        ["back"] = new Point(faceSize * 3, faceSize),
                        ["down"] = new Point(faceSize, faceSize * 2)
                    };

                    // Map stitching positions to preview positions
                    var stitchingToPreviewPosition = new Dictionary<string, int>
                    {
                        ["up"] = 0,     // Preview position 0 (top) -> stitching "up"
                        ["down"] = 1,   // Preview position 1 (bottom) -> stitching "down"
                        ["left"] = 2,   // Preview position 2 (left) -> stitching "left"
                        ["front"] = 3,  // Preview position 3 (center) -> stitching "front"
                        ["right"] = 4,  // Preview position 4 (right) -> stitching "right"
                        ["back"] = 5    // Preview position 5 (far right) -> stitching "back"
                    };

                    foreach (var stitchingPos in positions.Keys)
                    {
                        var previewPos = stitchingToPreviewPosition[stitchingPos];
                        var faceName = _positionToFace[previewPos]; // Get which face is currently in this preview position

                        if (_faceImages.TryGetValue(faceName, out var faceImage))
                        {
                            var rotatedImage = RotateImage(faceImage, _faceRotations[faceName]);

                            // Resize to faceSize x faceSize if needed
                            using (var resizedImage = new Bitmap(rotatedImage, new Size(faceSize, faceSize)))
                            {
                                var position = positions[stitchingPos];
                                // Draw with exact rectangle to avoid any gaps
                                graphics.DrawImage(resizedImage, 
                                    new Rectangle(position.X, position.Y, faceSize, faceSize),
                                    new Rectangle(0, 0, resizedImage.Width, resizedImage.Height),
                                    GraphicsUnit.Pixel);
                            }
                        }
                    }
                }

                return canvas;
            }
            catch (Exception ex)
            {
                LogMessage?.Invoke($"[Skybox] Stitching error: {ex.Message}");
                return null;
            }
        }

        private async Task<(bool success, string message)> ConvertVtfToPngAsync(string vtfPath, string outputDir = null)
        {
            if (string.IsNullOrEmpty(_vtfCmdPath) || !File.Exists(_vtfCmdPath))
            {
                return (false, "VTFCmd.exe is not available");
            }

            try
            {
                string baseName = Path.GetFileName(vtfPath);

                // Determine output directory
                if (string.IsNullOrEmpty(outputDir))
                {
                    outputDir = Path.GetDirectoryName(vtfPath) ?? ".";
                }

                // Ensure output directory exists
                Directory.CreateDirectory(outputDir);

                // Use absolute paths
                string absVtfPath = Path.GetFullPath(vtfPath);
                string absOutputDir = Path.GetFullPath(outputDir);

                // Get VTFCmd.exe directory to ensure VTFLib.dll is accessible
                string vtfCmdDir = Path.GetDirectoryName(_vtfCmdPath);
                string vtfLibPath = Path.Combine(vtfCmdDir, "VTFLib.dll");

                if (!File.Exists(vtfLibPath))
                {
                    return (false, $"VTFLib.dll not found at: {vtfLibPath}");
                }

                // VTFCmd.exe command for VTF to PNG conversion
                var startInfo = new ProcessStartInfo
                {
                    FileName = _vtfCmdPath,
                    Arguments = $"-file \"{absVtfPath}\" -output \"{absOutputDir}\" -exportformat png",
                    WorkingDirectory = absOutputDir,  // Set working directory to output directory
                    UseShellExecute = false,
                    CreateNoWindow = true,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true
                };

                using (var process = Process.Start(startInfo))
                {
                    if (process == null)
                    {
                        return (false, "Failed to start VTFCmd.exe");
                    }

                    await process.WaitForExitAsync();
                    
                    // Ensure process is completely finished
                    process.WaitForExit(1000);  // Additional synchronous wait
                    process.Close();
                    process.Dispose();

                    if (process.ExitCode != 0)
                    {
                        string error = await process.StandardError.ReadToEndAsync();
                        string errorMsg = string.IsNullOrEmpty(error) ? $"VTFCmd.exe failed with return code {process.ExitCode}" : error;
                        return (false, $"Conversion error: {errorMsg}");
                    }
                }

                // Check if output file was created
                string expectedPng = Path.Combine(absOutputDir, Path.GetFileNameWithoutExtension(baseName) + ".png");
                if (File.Exists(expectedPng))
                {
                    // Add a longer delay to ensure VTFCmd.exe has fully released the file
                    await Task.Delay(1000);  // 1 second delay
                    
                    // Try to validate the file by checking if we can open it
                    try
                    {
                        using (var testStream = File.OpenRead(expectedPng))
                        {
                            // File is accessible
                        }
                        return (true, expectedPng);
                    }
                    catch
                    {
                        // File is still locked, try one more time after additional delay
                        await Task.Delay(500);
                        return (true, expectedPng);
                    }
                }
                else
                {
                    return (false, "Output file was not created");
                }
            }
            catch (Exception ex)
            {
                return (false, $"Conversion error: {ex.Message}");
            }
        }

        private async Task<(bool success, string message)> ConvertImageMagickToPngAsync(string imagePath, string outputDir = null)
        {
            try
            {
                string baseName = Path.GetFileName(imagePath);

                // Determine output directory
                if (string.IsNullOrEmpty(outputDir))
                {
                    outputDir = Path.GetDirectoryName(imagePath) ?? ".";
                }

                // Ensure output directory exists
                Directory.CreateDirectory(outputDir);

                // Use absolute paths
                string absImagePath = Path.GetFullPath(imagePath);
                string absOutputDir = Path.GetFullPath(outputDir);

                // Output PNG path
                string expectedPng = Path.Combine(absOutputDir, Path.GetFileNameWithoutExtension(baseName) + ".png");

                // Convert using ImageMagick on a background thread to avoid blocking
                await Task.Run(() =>
                {
                    using (var image = new MagickImage(absImagePath))
                    {
                        // Set format to PNG
                        image.Format = MagickFormat.Png32;
                        
                        // Ensure proper color depth
                        image.Depth = 8;
                        
                        // Write to PNG
                        image.Write(expectedPng);
                    }
                });

                // Check if output file was created
                if (File.Exists(expectedPng))
                {
                    // Add a small delay to ensure file is fully written
                    await Task.Delay(100);
                    
                    // Try to validate the file by checking if we can open it
                    try
                    {
                        using (var testStream = File.OpenRead(expectedPng))
                        {
                            // File is accessible
                        }
                        return (true, expectedPng);
                    }
                    catch
                    {
                        // File is still locked, try one more time after additional delay
                        await Task.Delay(200);
                        return (true, expectedPng);
                    }
                }
                else
                {
                    return (false, "Output file was not created");
                }
            }
            catch (Exception ex)
            {
                return (false, $"Conversion error: {ex.Message}");
            }
        }

        private string ConvertPngToVtf(string pngPath, string outputDir, string skyboxName)
        {
            if (string.IsNullOrEmpty(_vtfCmdPath) || !File.Exists(_vtfCmdPath)) return null;

            try
            {
                var outputVtf = Path.Combine(outputDir, $"{skyboxName}.vtf");

                var startInfo = new ProcessStartInfo
                {
                    FileName = _vtfCmdPath,
                    Arguments = $"-file \"{pngPath}\" -output \"{outputDir}\" -exportformat vtf -format dxt1",
                    WorkingDirectory = Path.GetDirectoryName(_vtfCmdPath),
                    UseShellExecute = false,
                    CreateNoWindow = true,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true
                };

                using (var process = Process.Start(startInfo))
                {
                    if (process != null)
                    {
                        process.WaitForExit();
                        if (process.ExitCode == 0 && File.Exists(outputVtf))
                        {
                            return outputVtf;
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                LogMessage?.Invoke($"[Skybox] VTF creation error: {ex.Message}");
            }

            return null;
        }

        private void CreateSkyboxVmat(string outputDir, string skyboxName)
        {
            try
            {
                var vmatPath = Path.Combine(outputDir, $"skybox_{skyboxName}.vmat");
                var texturePath = $"materials/skybox/{skyboxName}.png";

                var vmatContent = $@"// THIS FILE IS AUTO-GENERATED (STANDARD SKYBOX)

Layer0
{{
    shader ""sky.vfx""

    //---- Format ----
    F_TEXTURE_FORMAT2 1 // Dxt1 (LDR)

    //---- Texture ----
    g_flBrightnessExposureBias ""0.000""
    g_flRenderOnlyExposureBias ""0.000""
    SkyTexture ""{texturePath}""

    VariableState
    {{
        ""Texture""
        {{
        }}
    }}
}}";

                File.WriteAllText(vmatPath, vmatContent);
                LogMessage?.Invoke($"[Skybox] Created skybox VMAT: {vmatPath}");
            }
            catch (Exception ex)
            {
                LogMessage?.Invoke($"[Skybox] Error creating skybox VMAT: {ex.Message}");
            }
        }

        private void CreateMoondomeVmat(string outputDir, string skyboxName)
        {
            try
            {
                var vmatPath = Path.Combine(outputDir, $"moondome_{skyboxName}.vmat");
                var texturePath = $"materials/skybox/{skyboxName}.png";

                var vmatContent = $@"// THIS FILE IS AUTO-GENERATED (MOONDOME)

Layer0
{{
    shader ""csgo_moondome.vfx""

    //---- Color ----
    g_flTexCoordRotation ""0.000""
    g_nScaleTexCoordUByModelScaleAxis ""0"" // None
    g_nScaleTexCoordVByModelScaleAxis ""0"" // None
    g_vColorTint ""[1.000000 1.000000 1.000000 0.000000]""
    g_vTexCoordCenter ""[0.500 0.500]""
    g_vTexCoordOffset ""[0.000 0.000]""
    g_vTexCoordScale ""[1.000 1.000]""
    g_vTexCoordScrollSpeed ""[0.000 0.000]""
    TextureColor ""[1.000000 1.000000 1.000000 0.000000]""

    //---- CubeParallax ----
    g_flCubeParallax ""0.000""

    //---- Fog ----
    g_bFogEnabled ""1""

    //---- Texture ----
    TextureCubeMap ""{texturePath}""

    //---- Texture Address Mode ----
    g_nTextureAddressModeU ""0"" // Wrap
    g_nTextureAddressModeV ""0"" // Wrap

    VariableState
    {{
        ""Color""
        {{
        }}
        ""CubeParallax""
        {{
        }}
    }}
}}";

                File.WriteAllText(vmatPath, vmatContent);
                LogMessage?.Invoke($"[Skybox] Created moondome VMAT: {vmatPath}");
            }
            catch (Exception ex)
            {
                LogMessage?.Invoke($"[Skybox] Error creating moondome VMAT: {ex.Message}");
            }
        }
    }
}