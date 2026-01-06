using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Net.Http;
using System.Threading.Tasks;
using System.Windows.Forms;

namespace CS2KZMappingTools
{
    public partial class VTF2PNGForm : Form
    {
        private readonly ThemeManager _themeManager;
        public event Action<string>? LogMessage;

        // UI Controls
        private Button? _selectFilesButton;
        private Button? _selectOutputButton;
        private Button? _convertButton;
        private ListBox? _filesListBox;
        private TextBox? _outputPathTextBox;
        private ProgressBar? _progressBar;

        // VTF Tools
        private string? _vtfCmdPath;
        private bool _vtfToolsAvailable = false;
        private List<string> _selectedFiles = new List<string>();

        public VTF2PNGForm(ThemeManager themeManager)
        {
            _themeManager = themeManager;
            InitializeComponent();
            InitializeVTF();
            ApplyTheme();
        }

        private void InitializeComponent()
        {
            this.Text = "VTF to PNG Converter";
            this.Size = new Size(600, 350);
            this.StartPosition = FormStartPosition.CenterParent;
            this.FormBorderStyle = FormBorderStyle.FixedDialog;
            this.MaximizeBox = false;
            this.MinimizeBox = false;

            // Select Files Button
            _selectFilesButton = new Button
            {
                Text = "Select VTF Files",
                Location = new Point(20, 20),
                Size = new Size(120, 35),
                FlatStyle = FlatStyle.Flat
            };
            _selectFilesButton.Click += SelectFilesButton_Click;

            // Files ListBox
            _filesListBox = new ListBox
            {
                Location = new Point(20, 65),
                Size = new Size(540, 150),
                SelectionMode = SelectionMode.MultiSimple
            };

            // Output Path TextBox
            _outputPathTextBox = new TextBox
            {
                Location = new Point(20, 230),
                Size = new Size(420, 25),
                Enabled = true
            };

            // Select Output Button
            _selectOutputButton = new Button
            {
                Text = "Browse...",
                Location = new Point(450, 228),
                Size = new Size(80, 27),
                FlatStyle = FlatStyle.Flat,
                Enabled = true
            };
            _selectOutputButton.Click += SelectOutputButton_Click;

            // Convert Button
            _convertButton = new Button
            {
                Text = "Convert to PNG",
                Location = new Point(20, 265),
                Size = new Size(120, 35),
                FlatStyle = FlatStyle.Flat,
                Enabled = false
            };
            _convertButton.Click += ConvertButton_Click;

            // Progress Bar
            _progressBar = new ProgressBar
            {
                Location = new Point(20, 315),
                Size = new Size(540, 25),
                Style = ProgressBarStyle.Continuous,
                Visible = false
            };

            this.Controls.AddRange(new Control[] {
                _selectFilesButton, _filesListBox,
                _outputPathTextBox, _selectOutputButton, _convertButton,
                _progressBar
            });
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
        }

        private async void InitializeVTF()
        {
            await Task.Run(() => FindOrDownloadVtfTools());
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
                    LogMessage?.Invoke($"[VTF] Using VTF tools from: {_vtfCmdPath}");
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
                        LogMessage?.Invoke($"[VTF] Using bundled VTF tools from: {_vtfCmdPath}");
                        return;
                    }
                }

                // Download VTF tools if not found anywhere
                Directory.CreateDirectory(toolsDir);

                LogMessage?.Invoke("[VTF] VTF tools not found. Downloading from GitHub...");
                LogMessage?.Invoke("[VTF] This is a one-time download (~2 MB)...");

                string downloadUrl = "https://nemstools.github.io/files/vtflib132-bin.zip";
                LogMessage?.Invoke($"[VTF] Downloading VTFLib binaries from {downloadUrl}...");

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
                                        LogMessage?.Invoke($"[VTF] Extracted {requiredFile.Key}");
                                        break;
                                    }
                                }
                            }
                        }

                        if (foundFiles.Contains("VTFCmd.exe") && foundFiles.Contains("VTFLib.dll"))
                        {
                            _vtfCmdPath = vtfCmdPath;
                            _vtfToolsAvailable = true;
                            LogMessage?.Invoke($"[VTF] VTF tools installed to: {toolsDir}");
                        }
                        else
                        {
                            LogMessage?.Invoke("[VTF] Failed to extract required VTF tools from archive");
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                LogMessage?.Invoke($"[VTF] Error initializing VTF tools: {ex.Message}");
            }
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
        }

        private void SelectFilesButton_Click(object? sender, EventArgs e)
        {
            using (var openFileDialog = new OpenFileDialog())
            {
                openFileDialog.Title = "Select VTF files to convert";
                openFileDialog.Filter = "VTF files (*.vtf)|*.vtf|All files (*.*)|*.*";
                openFileDialog.Multiselect = true;

                if (openFileDialog.ShowDialog() == DialogResult.OK)
                {
                    _selectedFiles = openFileDialog.FileNames.ToList();
                    UpdateFilesList();
                    UpdateConvertButton();
                    
                    // Set default output directory to the same as the first selected file
                    if (_selectedFiles.Count > 0 && string.IsNullOrEmpty(_outputPathTextBox.Text))
                    {
                        _outputPathTextBox.Text = Path.GetDirectoryName(_selectedFiles[0]);
                    }
                }
            }
        }

        private void SelectOutputButton_Click(object? sender, EventArgs e)
        {
            using (var folderBrowserDialog = new FolderBrowserDialog())
            {
                folderBrowserDialog.Description = "Select output directory for PNG files";

                if (folderBrowserDialog.ShowDialog() == DialogResult.OK)
                {
                    _outputPathTextBox.Text = folderBrowserDialog.SelectedPath;
                }
            }
        }

        private void UpdateFilesList()
        {
            _filesListBox.Items.Clear();
            foreach (var file in _selectedFiles)
            {
                _filesListBox.Items.Add(Path.GetFileName(file));
            }
        }

        private void UpdateConvertButton()
        {
            _convertButton.Enabled = _vtfToolsAvailable && _selectedFiles.Count > 0;
        }

        private async void ConvertButton_Click(object? sender, EventArgs e)
        {
            if (!_vtfToolsAvailable || _vtfCmdPath == null || _selectedFiles.Count == 0)
                return;

            string outputDir = !string.IsNullOrEmpty(_outputPathTextBox.Text)
                ? _outputPathTextBox.Text
                : null;

            _convertButton.Enabled = false;
            _progressBar.Visible = true;
            _progressBar.Value = 0;
            _progressBar.Maximum = _selectedFiles.Count;

            int converted = 0;
            int failed = 0;
            var results = new List<string>();

            foreach (var vtfFile in _selectedFiles)
            {
                var (success, message) = await ConvertVtfToPngAsync(vtfFile, outputDir);

                if (success)
                {
                    converted++;
                    results.Add($"[OK] {Path.GetFileName(vtfFile)} -> {Path.GetFileName(message)}");
                }
                else
                {
                    failed++;
                    results.Add($"[FAIL] {Path.GetFileName(vtfFile)}: {message}");
                }

                _progressBar.Value++;
                await Task.Delay(10); // Small delay for UI responsiveness
            }

            _progressBar.Visible = false;
            _convertButton.Enabled = true;

            // Show results
            string resultText = string.Join("\n", results);
            string summary = $"Conversion Complete!\n\nConverted: {converted}\nFailed: {failed}\n\n{resultText}";

            if (failed > 0)
            {
                MessageBox.Show(summary, "Conversion Complete (with errors)", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            }
            else
            {
                MessageBox.Show(summary, "Success", MessageBoxButtons.OK, MessageBoxIcon.Information);
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
                    WorkingDirectory = vtfCmdDir,
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
                    return (true, expectedPng);
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
    }
}