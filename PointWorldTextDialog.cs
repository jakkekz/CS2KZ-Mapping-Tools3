using System;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using System.Windows.Forms;
using Microsoft.Win32;

#nullable enable

namespace CS2KZMappingTools
{
    public partial class PointWorldTextDialog : Form
    {
        public event Action<string, string, int, int, bool, string?, string, float>? TextGenerated;
        
        private readonly ThemeManager _themeManager;
        
        private TextBox _textInput = null!;
        private RadioButton _size256Radio = null!;
        private RadioButton _size512Radio = null!;
        private RadioButton _size1024Radio = null!;
        private RadioButton _size2048Radio = null!;
        private TextBox _outputPathInput = null!;
        private Button _generateButton = null!;
        private Button _browseButton = null!;
        private CheckBox _generateVmatCheckbox = null!;
        private ComboBox _addonComboBox = null!;
        private RadioButton _customPathRadio = null!;
        private RadioButton _addonPathRadio = null!;
        private Label _statusLabel = null!;
        private TextBox _filenameInput = null!;
        private bool _filenameManuallyEdited = false;
        private PictureBox _previewPictureBox = null!;
        private TrackBar _scaleTrackBar = null!;
        private Label _scaleValueLabel = null!;
        private static readonly string TempPreviewPath = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Temp", ".CS2KZ-mapping-tools", "preview.png");

        public PointWorldTextDialog(ThemeManager themeManager)
        {
            _themeManager = themeManager;
            InitializeComponent();
            SetupTheme();
        }

        private void InitializeComponent()
        {
            Text = "point_worldtext Generator";
            Size = new Size(480, 650);
            StartPosition = FormStartPosition.CenterParent;
            FormBorderStyle = FormBorderStyle.FixedDialog;
            MaximizeBox = false;
            MinimizeBox = false;
            ShowInTaskbar = false;

            var panel = new TableLayoutPanel
            {
                Dock = DockStyle.Fill,
                ColumnCount = 4,
                RowCount = 17,
                Padding = new Padding(15)
            };

            // Setup column styles - make columns more equal for radio buttons
            panel.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 25F));
            panel.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 25F));
            panel.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 25F));
            panel.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 25F));

            // Row 0: Text input label
            var textLabel = new Label
            {
                Text = "Text to generate:",
                AutoSize = true,
                Anchor = AnchorStyles.Left | AnchorStyles.Top
            };
            panel.Controls.Add(textLabel, 0, 0);
            panel.SetColumnSpan(textLabel, 4);

            // Row 1: Text input
            _textInput = new TextBox
            {
                Multiline = true,
                Height = 60,
                ScrollBars = ScrollBars.Vertical,
                Anchor = AnchorStyles.Left | AnchorStyles.Right | AnchorStyles.Top,
                Text = "Hello World!"
            };
            panel.Controls.Add(_textInput, 0, 1);
            panel.SetColumnSpan(_textInput, 4);

            // Row 2: Size label
            var sizeLabel = new Label
            {
                Text = "Size:",
                AutoSize = true,
                Anchor = AnchorStyles.Left | AnchorStyles.Top
            };
            panel.Controls.Add(sizeLabel, 0, 2);
            panel.SetColumnSpan(sizeLabel, 4);

            // Row 3: Size radio buttons in a panel
            var sizePanel = new Panel
            {
                Height = 25,
                Anchor = AnchorStyles.Left | AnchorStyles.Right
            };
            
            _size256Radio = new RadioButton
            {
                Text = "256",
                AutoSize = true,
                Location = new Point(0, 0)
            };
            sizePanel.Controls.Add(_size256Radio);

            _size512Radio = new RadioButton
            {
                Text = "512",
                AutoSize = true,
                Checked = true,
                Location = new Point(60, 0)
            };
            sizePanel.Controls.Add(_size512Radio);

            _size1024Radio = new RadioButton
            {
                Text = "1024",
                AutoSize = true,
                Location = new Point(120, 0)
            };
            sizePanel.Controls.Add(_size1024Radio);

            _size2048Radio = new RadioButton
            {
                Text = "2048",
                AutoSize = true,
                Location = new Point(180, 0)
            };
            sizePanel.Controls.Add(_size2048Radio);
            
            panel.Controls.Add(sizePanel, 0, 3);
            panel.SetColumnSpan(sizePanel, 4);

            // Row 4: Text scale label
            var scaleLabel = new Label
            {
                Text = "Text scale:",
                AutoSize = true,
                Anchor = AnchorStyles.Left | AnchorStyles.Top
            };
            panel.Controls.Add(scaleLabel, 0, 4);
            panel.SetColumnSpan(scaleLabel, 4);

            // Row 5: Text scale trackbar with value label
            var scalePanel = new Panel
            {
                Height = 40,
                Anchor = AnchorStyles.Left | AnchorStyles.Right
            };
            
            _scaleTrackBar = new TrackBar
            {
                Minimum = 1,
                Maximum = 100,
                Value = 100,
                TickFrequency = 10,
                TickStyle = TickStyle.TopLeft,
                Width = 300,
                Location = new Point(0, 0)
            };
            _scaleTrackBar.ValueChanged += ScaleTrackBar_ValueChanged;
            scalePanel.Controls.Add(_scaleTrackBar);
            
            _scaleValueLabel = new Label
            {
                Text = "100%",
                AutoSize = true,
                Location = new Point(310, 10)
            };
            scalePanel.Controls.Add(_scaleValueLabel);
            
            panel.Controls.Add(scalePanel, 0, 5);
            panel.SetColumnSpan(scalePanel, 4);

            // Row 6: Preview image
            var previewLabel = new Label
            {
                Text = "Preview:",
                AutoSize = true,
                Anchor = AnchorStyles.Left | AnchorStyles.Top
            };
            panel.Controls.Add(previewLabel, 0, 6);
            panel.SetColumnSpan(previewLabel, 4);

            _previewPictureBox = new PictureBox
            {
                Width = 200,
                Height = 180,
                Anchor = AnchorStyles.Left | AnchorStyles.Top,
                SizeMode = PictureBoxSizeMode.Zoom,
                BorderStyle = BorderStyle.FixedSingle,
                BackColor = Color.Black
            };
            panel.Controls.Add(_previewPictureBox, 0, 7);
            panel.SetColumnSpan(_previewPictureBox, 4);

            // Row 8: Generate .vmat checkbox
            _generateVmatCheckbox = new CheckBox
            {
                Text = "Generate .vmat file",
                AutoSize = true,
                Checked = true,
                Anchor = AnchorStyles.Left
            };
            panel.Controls.Add(_generateVmatCheckbox, 0, 8);
            panel.SetColumnSpan(_generateVmatCheckbox, 4);

            // Row 9: Output path options
            var pathLabel = new Label
            {
                Text = "Output location:",
                AutoSize = true,
                Anchor = AnchorStyles.Left | AnchorStyles.Top
            };
            panel.Controls.Add(pathLabel, 0, 9);
            panel.SetColumnSpan(pathLabel, 4);

            // Row 10: Path selection radio buttons in a panel
            var pathPanel = new Panel
            {
                Height = 25,
                Anchor = AnchorStyles.Left | AnchorStyles.Right
            };
            
            _addonPathRadio = new RadioButton
            {
                Text = "CS2 Addon:",
                AutoSize = true,
                Checked = true,
                Location = new Point(0, 0)
            };
            pathPanel.Controls.Add(_addonPathRadio);
            
            _customPathRadio = new RadioButton
            {
                Text = "Custom path:",
                AutoSize = true,
                Location = new Point(120, 0)
            };
            pathPanel.Controls.Add(_customPathRadio);
            
            panel.Controls.Add(pathPanel, 0, 10);
            panel.SetColumnSpan(pathPanel, 4);

            // Row 9: Addon combo box
            _addonComboBox = new ComboBox
            {
                DropDownStyle = ComboBoxStyle.DropDownList,
                Anchor = AnchorStyles.Left | AnchorStyles.Right,
                Width = 200
            };
            LoadAvailableAddons();
            panel.Controls.Add(_addonComboBox, 0, 11);
            panel.SetColumnSpan(_addonComboBox, 4);

            // Row 11: Custom path input (initially hidden) - same row as addon dropdown
            _outputPathInput = new TextBox
            {
                Anchor = AnchorStyles.Left | AnchorStyles.Right | AnchorStyles.Top,
                Text = Environment.GetFolderPath(Environment.SpecialFolder.Desktop),
                PlaceholderText = "Select output directory",
                Visible = false
            };
            panel.Controls.Add(_outputPathInput, 0, 11);
            panel.SetColumnSpan(_outputPathInput, 3);

            _browseButton = new Button
            {
                Text = "Browse...",
                Width = 75,
                Anchor = AnchorStyles.Right,
                Visible = false
            };
            _browseButton.Click += BrowseButton_Click;
            panel.Controls.Add(_browseButton, 3, 11);

            // Row 12: Filename input
            var filenameLabel = new Label
            {
                Text = "Filename:",
                AutoSize = true,
                Anchor = AnchorStyles.Left | AnchorStyles.Top
            };
            panel.Controls.Add(filenameLabel, 0, 12);
            panel.SetColumnSpan(filenameLabel, 4);

            _filenameInput = new TextBox
            {
                Anchor = AnchorStyles.Left | AnchorStyles.Right,
                PlaceholderText = "Auto-generates from text above (or enter custom name)"
            };
            _filenameInput.TextChanged += FilenameInput_TextChanged;
            panel.Controls.Add(_filenameInput, 0, 13);
            panel.SetColumnSpan(_filenameInput, 4);

            // Row 14: Generate button
            _generateButton = new Button
            {
                Text = "Generate point_worldtext",
                Height = 32,
                Anchor = AnchorStyles.Left | AnchorStyles.Right
            };
            _generateButton.Click += GenerateButton_Click;
            panel.Controls.Add(_generateButton, 0, 14);
            panel.SetColumnSpan(_generateButton, 4);

            // Row 15: Status label (closer to generate button)
            _statusLabel = new Label
            {
                Text = "",
                AutoSize = true,
                Anchor = AnchorStyles.Left | AnchorStyles.Top,
                ForeColor = Color.Green,
                Margin = new Padding(0, 2, 0, 0)
            };
            panel.Controls.Add(_statusLabel, 0, 15);
            panel.SetColumnSpan(_statusLabel, 4);

            // Event handlers for radio buttons
            _addonPathRadio.CheckedChanged += (s, e) => UpdatePathControls();
            _customPathRadio.CheckedChanged += (s, e) => UpdatePathControls();
            
            // Initialize filename preview
            UpdateFilenamePreview();
            
            // Update preview when main text changes
            _textInput.TextChanged += (s, e) => UpdateFilenamePreview();
            
            // Update preview when size changes
            _size256Radio.CheckedChanged += (s, e) => { if (_size256Radio.Checked) UpdatePreviewImage(); };
            _size512Radio.CheckedChanged += (s, e) => { if (_size512Radio.Checked) UpdatePreviewImage(); };
            _size1024Radio.CheckedChanged += (s, e) => { if (_size1024Radio.Checked) UpdatePreviewImage(); };
            _size2048Radio.CheckedChanged += (s, e) => { if (_size2048Radio.Checked) UpdatePreviewImage(); };

            Controls.Add(panel);
        }

        private void SetupTheme()
        {
            var theme = _themeManager.GetCurrentTheme();
            
            // Apply theme to form
            BackColor = theme.WindowBackground;
            ForeColor = theme.Text;

            foreach (Control control in Controls)
            {
                ApplyThemeToControl(control);
            }
        }

        private void UpdatePathControls()
        {
            if (_addonPathRadio.Checked)
            {
                // Show addon controls, hide custom path controls
                _addonComboBox.Visible = true;
                _outputPathInput.Visible = false;
                _browseButton.Visible = false;
            }
            else
            {
                // Hide addon controls, show custom path controls
                _addonComboBox.Visible = false;
                _outputPathInput.Visible = true;
                _browseButton.Visible = true;
            }
        }
        
        private string? FindCs2Path()
        {
            try
            {
                // Get Steam path from registry
                using var key = Registry.CurrentUser.OpenSubKey(@"Software\Valve\Steam");
                if (key?.GetValue("SteamPath") is string steamPath)
                {
                    var libraryFoldersPath = Path.Combine(steamPath, "steamapps", "libraryfolders.vdf");
                    var cs2Path = FindCs2LibraryPath(libraryFoldersPath);

                    if (!string.IsNullOrEmpty(cs2Path))
                    {
                        var appManifestPath = Path.Combine(cs2Path, "steamapps", "appmanifest_730.acf");
                        if (File.Exists(appManifestPath))
                        {
                            // Parse the VDF file to get install directory
                            var installDir = ParseAppManifest(appManifestPath);
                            if (!string.IsNullOrEmpty(installDir))
                            {
                                cs2Path = Path.Combine(cs2Path, "steamapps", "common", installDir);
                                return cs2Path;
                            }
                        }
                    }
                }
            }
            catch
            {
                // Handle error silently for dialog
            }

            return null;
        }

        private string? FindCs2LibraryPath(string libraryFoldersPath)
        {
            if (!File.Exists(libraryFoldersPath)) return null;

            try
            {
                var content = File.ReadAllText(libraryFoldersPath);
                // Simple VDF parsing - look for library folders containing app 730
                var lines = content.Split('\n');
                string currentPath = null;

                foreach (var line in lines)
                {
                    var trimmed = line.Trim();
                    if (trimmed.Contains("\"path\""))
                    {
                        var match = Regex.Match(trimmed, "\"path\"\\s+\"([^\"]+)\"");
                        if (match.Success)
                        {
                            currentPath = match.Groups[1].Value.Replace("\\\\", "\\");
                        }
                    }
                    else if (trimmed.Contains("\"730\"") && currentPath != null)
                    {
                        return currentPath;
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
        
        private void LoadAvailableAddons()
        {
            try
            {
                var cs2Path = FindCs2Path();
                if (string.IsNullOrEmpty(cs2Path))
                {
                    _addonComboBox.Items.Add("CS2 installation not found");
                    _addonComboBox.SelectedIndex = 0;
                    _addonComboBox.Enabled = false;
                    _addonPathRadio.Enabled = false;
                    _customPathRadio.Checked = true;
                    return;
                }

                var addonsPath = Path.Combine(cs2Path, "content", "csgo_addons");
                if (Directory.Exists(addonsPath))
                {
                    var addonDirs = Directory.GetDirectories(addonsPath)
                        .Select(Path.GetFileName)
                        .Where(name => !string.IsNullOrEmpty(name) && 
                                      !name.Equals("addon_template", StringComparison.OrdinalIgnoreCase) &&
                                      !name.Equals("addontemplate", StringComparison.OrdinalIgnoreCase))
                        .OrderBy(name => name)
                        .Cast<object>()
                        .ToArray();
                    
                    if (addonDirs.Length > 0)
                    {
                        _addonComboBox.Items.AddRange(addonDirs);
                        _addonComboBox.SelectedIndex = 0;
                    }
                    else
                    {
                        _addonComboBox.Items.Add("No addons found (create one in CS2 Workshop Tools first)");
                        _addonComboBox.SelectedIndex = 0;
                        _addonComboBox.Enabled = false;
                        _addonPathRadio.Enabled = false;
                        _customPathRadio.Checked = true;
                    }
                }
                else
                {
                    // Try to create the addons directory
                    try
                    {
                        Directory.CreateDirectory(addonsPath);
                        _addonComboBox.Items.Add("No addons found (create one in CS2 Workshop Tools first)");
                        _addonComboBox.SelectedIndex = 0;
                        _addonComboBox.Enabled = false;
                        _addonPathRadio.Enabled = false;
                        _customPathRadio.Checked = true;
                    }
                    catch (Exception ex)
                    {
                        MessageBox.Show($"Cannot access CS2 addons folder at {addonsPath}.\nError: {ex.Message}\n\nPlease ensure CS2 Workshop Tools is installed and you have write access to the CS2 directory.", "Access Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
                        _addonComboBox.Items.Add("Cannot access CS2 addons folder");
                        _addonComboBox.SelectedIndex = 0;
                        _addonComboBox.Enabled = false;
                        _addonPathRadio.Enabled = false;
                        _customPathRadio.Checked = true;
                    }
                }
            }
            catch (Exception ex)
            {
                _addonComboBox.Items.Add($"Error loading addons: {ex.Message}");
                _addonComboBox.SelectedIndex = 0;
                _addonComboBox.Enabled = false;
                _addonPathRadio.Enabled = false;
                _customPathRadio.Checked = true;
            }
        }
        
        private void ApplyThemeToControl(Control control)
        {
            var theme = _themeManager.GetCurrentTheme();
            
            if (control is TextBox textBox)
            {
                textBox.BackColor = theme.ButtonBackground; // Use existing theme property
                textBox.ForeColor = theme.Text;
                textBox.BorderStyle = BorderStyle.FixedSingle;
            }
            else if (control is Button button)
            {
                button.BackColor = theme.ButtonBackground;
                button.ForeColor = theme.Text; // Use Text property
                button.FlatStyle = FlatStyle.Flat;
                button.FlatAppearance.BorderColor = theme.Border;
            }
            else if (control is Label label)
            {
                label.ForeColor = theme.Text;
            }
            else if (control is CheckBox checkBox)
            {
                checkBox.ForeColor = theme.Text;
            }
            else if (control is RadioButton radioButton)
            {
                radioButton.ForeColor = theme.Text;
            }
            else if (control is ComboBox comboBox)
            {
                comboBox.BackColor = theme.ButtonBackground; // Use existing theme property
                comboBox.ForeColor = theme.Text;
            }
            else if (control is PictureBox pictureBox)
            {
                pictureBox.BackColor = theme.WindowBackground;
            }
            else if (control is TrackBar trackBar)
            {
                trackBar.BackColor = theme.WindowBackground;
            }
            
            // Apply theme recursively to child controls
            foreach (Control child in control.Controls)
            {
                ApplyThemeToControl(child);
            }

            // Recursively apply to child controls
            foreach (Control childControl in control.Controls)
            {
                ApplyThemeToControl(childControl);
            }
        }

        private void BrowseButton_Click(object? sender, EventArgs e)
        {
            using var dialog = new FolderBrowserDialog
            {
                Description = "Select output folder for the generated image",
                UseDescriptionForTitle = true,
                InitialDirectory = Environment.GetFolderPath(Environment.SpecialFolder.Desktop)
            };

            if (dialog.ShowDialog() == DialogResult.OK)
            {
                _outputPathInput.Text = dialog.SelectedPath;
            }
        }

        private void GenerateButton_Click(object? sender, EventArgs e)
        {
            var text = _textInput.Text.Trim();
            if (string.IsNullOrEmpty(text))
            {
                MessageBox.Show("Please enter some text to generate.", "No Text", 
                    MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            string? outputPath;
            if (_addonPathRadio.Checked && _addonComboBox.SelectedItem != null)
            {
                var addonName = _addonComboBox.SelectedItem.ToString();
                if (!string.IsNullOrEmpty(addonName) && !addonName.Contains("Error") && !addonName.Contains("not found"))
                {
                    outputPath = null; // Will be handled by manager with addon name
                }
                else
                {
                    MessageBox.Show("Please select a valid addon.", "Invalid Addon", 
                        MessageBoxButtons.OK, MessageBoxIcon.Warning);
                    return;
                }
            }
            else
            {
                var directoryPath = _outputPathInput.Text.Trim();
                if (string.IsNullOrEmpty(directoryPath))
                {
                    MessageBox.Show("Please specify an output directory.", "No Output Directory", 
                        MessageBoxButtons.OK, MessageBoxIcon.Warning);
                    return;
                }
                
                // Combine directory and filename (filename will be determined below)
                outputPath = directoryPath; // We'll add filename later
            }

            var size = GetSelectedSize();
            var generateVmat = _generateVmatCheckbox.Checked;
            var selectedAddon = _addonPathRadio.Checked ? _addonComboBox.SelectedItem?.ToString() : null;
            var customFilename = _filenameInput.Text.Trim();
            var finalFilename = !string.IsNullOrEmpty(customFilename) ? SanitizeFilename(customFilename) : SanitizeFilename(text);
            
            // For custom path, combine directory with filename
            if (_customPathRadio.Checked)
            {
                outputPath = Path.Combine(outputPath!, $"{finalFilename}.png");
            }
            
            var scaleFactor = _scaleTrackBar.Value / 100.0f;

            // Fire the event with all parameters including filename and scale
            TextGenerated?.Invoke(text, outputPath ?? "", size, size, generateVmat, selectedAddon, finalFilename, scaleFactor);

            // Show success message instead of closing
            _statusLabel.Text = $"{finalFilename} made successfully!";
        }
        
        private int GetSelectedSize()
        {
            if (_size256Radio.Checked) return 256;
            if (_size512Radio.Checked) return 512;
            if (_size1024Radio.Checked) return 1024;
            if (_size2048Radio.Checked) return 2048;
            return 512; // Default
        }
        
        private void FilenameInput_TextChanged(object? sender, EventArgs e)
        {
            // Check if this change was caused by auto-update or manual edit
            var currentText = _textInput.Text.Trim();
            var expectedAutoFilename = !string.IsNullOrEmpty(currentText) ? SanitizeFilename(currentText) : "";
            
            // If the filename doesn't match what would be auto-generated, mark as manually edited
            _filenameManuallyEdited = _filenameInput.Text != expectedAutoFilename;
            
            // If user cleared the field, reset to auto-generation mode
            if (string.IsNullOrEmpty(_filenameInput.Text))
            {
                _filenameManuallyEdited = false;
                UpdateFilenamePreview();
            }
        }
        
        private void UpdateFilenamePreview()
        {
            // Only auto-update if filename hasn't been manually edited
            if (!_filenameManuallyEdited)
            {
                var inputText = _textInput.Text.Trim();
                if (!string.IsNullOrEmpty(inputText))
                {
                    var sanitizedFilename = SanitizeFilename(inputText);
                    _filenameInput.Text = sanitizedFilename;
                }
                else
                {
                    _filenameInput.Text = "";
                }
            }
            
            // Update preview when filename or text changes
            UpdatePreviewImage();
        }
        
        private string SanitizeFilename(string input)
        {
            if (string.IsNullOrEmpty(input)) return "pointworldtext";
            
            // Keep only letters, numbers, and convert spaces to underscores
            var result = System.Text.RegularExpressions.Regex.Replace(input, @"[^a-zA-Z0-9\s]", "");
            result = result.Replace(" ", "_");
            result = result.Trim('_');
            
            return string.IsNullOrEmpty(result) ? "pointworldtext" : result;
        }
        
        private void UpdatePreviewImage()
        {
            try
            {
                var text = _textInput.Text.Trim();
                if (string.IsNullOrEmpty(text))
                {
                    _previewPictureBox.Image?.Dispose();
                    _previewPictureBox.Image = null;
                    return;
                }
                
                var size = GetSelectedSize();
                var scale = _scaleTrackBar.Value / 100.0f;
                
                // Create temp directory if it doesn't exist
                Directory.CreateDirectory(Path.GetDirectoryName(TempPreviewPath)!);
                
                // Delete old preview file if it exists
                if (File.Exists(TempPreviewPath))
                {
                    File.Delete(TempPreviewPath);
                }
                
                // Generate preview using PointWorldTextManager
                var previewPath = GeneratePreview(text, size, scale);
                
                if (previewPath != null && File.Exists(previewPath))
                {
                    // Load image into PictureBox
                    _previewPictureBox.Image?.Dispose();
                    using (var fs = new FileStream(previewPath, FileMode.Open, FileAccess.Read))
                    {
                        _previewPictureBox.Image = new Bitmap(fs);
                    }
                }
            }
            catch (Exception)
            {
                // If preview generation fails, just clear the preview
                _previewPictureBox.Image?.Dispose();
                _previewPictureBox.Image = null;
            }
        }
        
        private string? GeneratePreview(string text, int size, float scale = 1.0f)
        {
            try
            {
                // Create a temporary PointWorldTextManager instance for preview generation
                var previewManager = new PointWorldTextManager();
                
                // Generate preview directly to temp path with scale factor
                var result = previewManager.GenerateTextWithOptions(text, TempPreviewPath, size, size, false, null, "preview", scale);
                
                return result != null ? TempPreviewPath : null;
            }
            catch (Exception ex)
            {
                // Show error for debugging
                MessageBox.Show($"Preview generation failed: {ex.Message}", "Preview Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return null;
            }
        }
        
        private void ScaleTrackBar_ValueChanged(object? sender, EventArgs e)
        {
            _scaleValueLabel.Text = $"{_scaleTrackBar.Value}%";
            UpdatePreviewImage();
        }
        
        protected override void Dispose(bool disposing)
        {
            base.Dispose(disposing);
        }
    }
}