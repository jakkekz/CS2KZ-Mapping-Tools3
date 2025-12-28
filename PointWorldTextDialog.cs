using System;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Windows.Forms;

namespace CS2KZMappingTools
{
    public partial class PointWorldTextDialog : Form
    {
        public event Action<string, string, int, int, bool, string?, string>? TextGenerated;
        
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
        private Label _filenamePreviewLabel = null!;

        public PointWorldTextDialog(ThemeManager themeManager)
        {
            _themeManager = themeManager;
            InitializeComponent();
            SetupTheme();
        }

        private void InitializeComponent()
        {
            Text = "point_worldtext Generator";
            Size = new Size(480, 400);
            StartPosition = FormStartPosition.CenterParent;
            FormBorderStyle = FormBorderStyle.FixedDialog;
            MaximizeBox = false;
            MinimizeBox = false;
            ShowInTaskbar = false;

            var panel = new TableLayoutPanel
            {
                Dock = DockStyle.Fill,
                ColumnCount = 4,
                RowCount = 14,
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

            // Row 4: Generate .vmat checkbox
            _generateVmatCheckbox = new CheckBox
            {
                Text = "Generate .vmat file",
                AutoSize = true,
                Checked = true,
                Anchor = AnchorStyles.Left
            };
            panel.Controls.Add(_generateVmatCheckbox, 0, 4);
            panel.SetColumnSpan(_generateVmatCheckbox, 4);

            // Row 5: Filename input
            var filenameLabel = new Label
            {
                Text = "Filename (optional):",
                AutoSize = true,
                Anchor = AnchorStyles.Left | AnchorStyles.Top
            };
            panel.Controls.Add(filenameLabel, 0, 5);
            panel.SetColumnSpan(filenameLabel, 4);

            _filenameInput = new TextBox
            {
                Anchor = AnchorStyles.Left | AnchorStyles.Right,
                PlaceholderText = "Leave empty for auto-generated name"
            };
            _filenameInput.TextChanged += FilenameInput_TextChanged;
            panel.Controls.Add(_filenameInput, 0, 6);
            panel.SetColumnSpan(_filenameInput, 4);

            // Row 7: Filename preview
            _filenamePreviewLabel = new Label
            {
                Text = "File will be named: (enter text above to see preview)",
                AutoSize = true,
                Anchor = AnchorStyles.Left,
                ForeColor = Color.Gray,
                Font = new Font(Font.FontFamily, Font.Size * 0.9f, FontStyle.Italic)
            };
            panel.Controls.Add(_filenamePreviewLabel, 0, 7);
            panel.SetColumnSpan(_filenamePreviewLabel, 4);

            // Row 8: Output path options
            var pathLabel = new Label
            {
                Text = "Output location:",
                AutoSize = true,
                Anchor = AnchorStyles.Left | AnchorStyles.Top
            };
            panel.Controls.Add(pathLabel, 0, 8);
            panel.SetColumnSpan(pathLabel, 4);

            // Row 9: Path selection radio buttons in a panel
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
            
            panel.Controls.Add(pathPanel, 0, 9);
            panel.SetColumnSpan(pathPanel, 4);

            // Row 10: Addon combo box
            _addonComboBox = new ComboBox
            {
                DropDownStyle = ComboBoxStyle.DropDownList,
                Anchor = AnchorStyles.Left | AnchorStyles.Right,
                Width = 200
            };
            LoadAvailableAddons();
            panel.Controls.Add(_addonComboBox, 0, 10);
            panel.SetColumnSpan(_addonComboBox, 4);

            // Row 11: Custom path input (initially hidden)
            _outputPathInput = new TextBox
            {
                Anchor = AnchorStyles.Left | AnchorStyles.Right | AnchorStyles.Top,
                Text = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Desktop), "text_output.png"),
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

            // Row 12: Generate button
            _generateButton = new Button
            {
                Text = "Generate point_worldtext",
                Height = 32,
                Anchor = AnchorStyles.Left | AnchorStyles.Right
            };
            _generateButton.Click += GenerateButton_Click;
            panel.Controls.Add(_generateButton, 0, 12);
            panel.SetColumnSpan(_generateButton, 4);

            // Row 13: Status label (right under generate button)
            _statusLabel = new Label
            {
                Text = "",
                AutoSize = true,
                Anchor = AnchorStyles.Left,
                ForeColor = Color.Green
            };
            panel.Controls.Add(_statusLabel, 0, 13);
            panel.SetColumnSpan(_statusLabel, 4);

            // Event handlers for radio buttons
            _addonPathRadio.CheckedChanged += (s, e) => UpdatePathControls();
            _customPathRadio.CheckedChanged += (s, e) => UpdatePathControls();
            
            // Initialize filename preview
            UpdateFilenamePreview();
            
            // Update preview when main text changes
            _textInput.TextChanged += (s, e) => UpdateFilenamePreview();

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
        
        private void LoadAvailableAddons()
        {
            try
            {
                var addonsPath = @"D:\SteamLibrary\steamapps\common\Counter-Strike Global Offensive\content\csgo_addons";
                if (Directory.Exists(addonsPath))
                {
                    var addonDirs = Directory.GetDirectories(addonsPath)
                        .Select(Path.GetFileName)
                        .Where(name => !string.IsNullOrEmpty(name))
                        .OrderBy(name => name)
                        .Cast<object>()
                        .ToArray();
                    
                    _addonComboBox.Items.AddRange(addonDirs);
                    
                    if (_addonComboBox.Items.Count > 0)
                    {
                        _addonComboBox.SelectedIndex = 0;
                    }
                }
                else
                {
                    _addonComboBox.Items.Add("CS2 addons folder not found");
                    _addonComboBox.SelectedIndex = 0;
                    _addonComboBox.Enabled = false;
                    _addonPathRadio.Enabled = false;
                    _customPathRadio.Checked = true;
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
            using var dialog = new SaveFileDialog
            {
                Filter = "PNG Images|*.png",
                DefaultExt = "png",
                FileName = "text_output.png"
            };

            if (dialog.ShowDialog() == DialogResult.OK)
            {
                _outputPathInput.Text = dialog.FileName;
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
                outputPath = _outputPathInput.Text.Trim();
                if (string.IsNullOrEmpty(outputPath))
                {
                    MessageBox.Show("Please specify an output file path.", "No Output Path", 
                        MessageBoxButtons.OK, MessageBoxIcon.Warning);
                    return;
                }
            }

            var size = GetSelectedSize();
            var generateVmat = _generateVmatCheckbox.Checked;
            var selectedAddon = _addonPathRadio.Checked ? _addonComboBox.SelectedItem?.ToString() : null;
            var customFilename = _filenameInput.Text.Trim();
            var finalFilename = !string.IsNullOrEmpty(customFilename) ? SanitizeFilename(customFilename) : SanitizeFilename(text);

            // Fire the event with all parameters including filename
            TextGenerated?.Invoke(text, outputPath ?? "", size, size, generateVmat, selectedAddon, finalFilename);

            // Show success message instead of closing
            _statusLabel.Text = $"{text} made successfully!";
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
            UpdateFilenamePreview();
        }
        
        private void UpdateFilenamePreview()
        {
            var inputText = _textInput.Text.Trim();
            var customFilename = _filenameInput.Text.Trim();
            
            string filename;
            if (!string.IsNullOrEmpty(customFilename))
            {
                filename = SanitizeFilename(customFilename);
            }
            else if (!string.IsNullOrEmpty(inputText))
            {
                filename = SanitizeFilename(inputText);
            }
            else
            {
                filename = "pointworldtext";
            }
            
            _filenamePreviewLabel.Text = $"File will be named: {filename}.png";
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
        
        protected override void Dispose(bool disposing)
        {
            base.Dispose(disposing);
        }
    }
}